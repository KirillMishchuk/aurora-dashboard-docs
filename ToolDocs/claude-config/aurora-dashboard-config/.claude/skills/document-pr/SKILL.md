---
name: document-pr
description: >-
  Fetch a GitHub pull request against aurora-dashboard (by number, URL, or the
  current branch's PR) via `gh`, and produce one combined Russian-language
  report that (1) describes what the PR does and how — with verbatim code
  excerpts and file:line citations — (2) traces what it impacts, including
  consumers elsewhere in the monorepo beyond the PR's own changed files, and
  (3) reviews it for bugs, CLAUDE.md compliance, and simplification, using
  confidence-scored findings so only real issues surface. Saves the result as
  a markdown file in ../DOCS/aurora-dashboard-kb/prs/ and updates its index.
  Use whenever the user asks to document, разобрать, задокументировать,
  проанализировать a specific merged or open PR by number/URL for the
  knowledge base, or wants "full analysis + review" of a PR going into main —
  not for reviewing the current uncommitted working diff (that's
  `code-review`).
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
  the whole file. Get real line numbers from `git grep -n` or `cat -n`-style
  reads against the head commit blob.
- **Findings need a confidence pass before they're reported as issues** (see
  Step 5). An unfiltered "here's everything that looks off" list is not a
  review, it's noise — this mirrors the project's `code-review` skill.
- Report body is Russian, matching the KB's `README.md`. Code, identifiers,
  and file paths stay as-is (English/code, unchanged).

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

### 2. Get the diff and the head commit locally

```bash
gh pr diff <number> > /tmp/pr-<number>.diff   # or read directly, no need to save if small
git fetch origin <headRefOid>
```

The fetch makes `<headRefOid>` available locally as a plain object without
creating or checking out a branch — safe to do from whatever branch the user
currently has checked out. Use this SHA for every "what does the code
actually look like" lookup in the steps below (`git show <sha>:<path>`,
`git grep -n ... <sha> -- <pathspec>`).

### 3. Gather relevant CLAUDE.md files

Same move as the `code-review` command: list (don't read yet) the root
`CLAUDE.md` plus any `CLAUDE.md` in directories the
PR's changed files live under. Read them when you actually need to check a
specific claim in Steps 4 or 5 — no need to load everything up front.

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
git grep -n '<symbolName>' <headRefOid> -- '*.ts' '*.tsx'
```

Report what you find: which other packages/apps/routes depend on the
changed surface, whether the PR updated all of them consistently or left a
caller stale (that's worth flagging even outside the formal review pass —
it's exactly the kind of thing a descriptive walkthrough should catch), and
whether the change is internal-only (no outside consumers found) versus a
contract change that ripples outward (e.g. changes to `AuroraRouter`,
anything under `packages/aurora/src/server/*/routers/`, or exported client
hooks/components other apps import).

### 5. Review pass

Reuse the review methodology from the project's `code-review` command
(`gh`-based PR review), adapted to feed a report instead of a PR comment —
don't redo the eligibility/"already reviewed" gating from that command
(irrelevant here: this skill runs on merged PRs for documentation purposes,
not to gate a merge), and don't post anything to GitHub.

1. Launch 5 parallel Sonnet agents against the diff + CLAUDE.md file list
   from Step 3 (give them the diff directly, they don't need to re-fetch
   it):
   a. **CLAUDE.md compliance** — audit against the gathered CLAUDE.md files.
      Remember CLAUDE.md is guidance for writing code; not every line
      applies to review.
   b. **Bug scan** — shallow scan of the diff itself for obvious bugs. Don't
      wander into unrelated context; focus on large bugs, skip nitpicks.
   c. **Historical context** — `git log`/`git blame` on the modified files
      to catch bugs that only make sense in light of history.
   d. **Prior PR feedback** — `gh pr list --search` / `git log` on these
      files for earlier PRs; check whether old review comments still apply.
      Best-effort — don't burn much time if nothing turns up quickly.
   e. **Comment compliance** — read code comments in the modified files,
      check the change complies with any guidance those comments state.
   Each agent returns a list of issues with the reason each was flagged.
2. For every issue from step 1, launch a Haiku confidence-scoring agent with
   the PR, the issue, and the CLAUDE.md file list. Score 0-100 using this
   rubric (give it verbatim):
   - **0**: not confident at all — false positive or pre-existing issue.
   - **25**: might be real, might not; agent couldn't verify. If stylistic,
     not explicitly called out in the relevant CLAUDE.md.
   - **50**: verified real, but a nitpick or rare in practice; not very
     important relative to the rest of the PR.
   - **75**: highly confident — double-checked, will likely be hit in
     practice, existing approach is insufficient, or directly called out in
     CLAUDE.md.
   - **100**: absolutely certain, confirmed by direct evidence, will happen
     frequently.
3. Keep only issues scoring ≥80. If none clear that bar, the review section
   says so plainly — don't manufacture nitpicks to fill space.

False positives to exclude (same list `code-review` uses — it's good and
applies here unchanged): pre-existing issues; things that look like bugs but
aren't; pedantic nitpicks a senior engineer wouldn't raise; anything a
linter/typechecker/CI would catch (don't run builds yourself — assume CI
covers this); general code-quality opinions (test coverage, security,
docs) unless CLAUDE.md explicitly requires them; issues explicitly silenced
in code (lint-ignore comments); intentional changes that are clearly part of
the broader PR; real issues on lines the PR didn't touch.

### 6. Write the report

Resolve the target directory from the repo root, not from the shell's
current directory — a bare `../DOCS` typed from a subdirectory folds into
this repo's own git-tracked `docs/` folder on macOS:

```bash
PRS_DIR="$(dirname "$(git rev-parse --show-toplevel)")/DOCS/aurora-dashboard-kb/prs"
mkdir -p "$PRS_DIR"
```

File name:
`<number>-<kebab-slug-of-title>.md`, e.g. `1079-slot-support-login.md`.

Use this template:

```markdown
# PR #<number>: <title>

**Автор:** <author> · **Статус:** <merged DD.MM.YYYY / open / draft / closed>
**Ветки:** `<headRefName>` → `<baseRefName>` · **Файлов:** <changedFiles> (+<additions>/-<deletions>)
**Ссылка:** <url>

> Если `baseRefName` ≠ `main`, отметить это явно здесь.

## Что сделано

<narrative — the story of the change, grouped by area, not a file list>

## Как это реализовано

<walkthrough with verbatim excerpts and file:line citations, at <headRefOid>>

## Что затронуло

<impact/blast-radius findings from Step 4 — consumers found elsewhere in the
monorepo, contract changes, anything left inconsistent>

## Ревью

<findings scoring ≥80, each with: description, why it was flagged, and a
file:line citation — or "проблем с уверенностью ≥80 не найдено" if none>

---
Проанализировано: <today's date> · коммит `<headRefOid short sha>`
```

### 7. Update the index

Maintain `$PRS_DIR/README.md` as a lookup table,
newest first:

```markdown
# PR-отчёты

| PR | Дата | Заголовок | Затронуло | Файл |
| --- | --- | --- | --- | --- |
| [#1079](https://github.com/.../pull/1079) | 16.07.2026 | fix(aurora): add slot support again for custom login component | `slots.login`, `LoginForm` | [1079-slot-support-login.md](./1079-slot-support-login.md) |
```

If the file doesn't exist yet, create it with this header and one row. If it
exists, insert the new row directly below the header (keep the full history,
newest on top — same principle as the KB's own update log: don't trim).

### 8. Report back

Tell the user, briefly: what PR was analyzed, the file path you wrote, and
one line on what the review pass found (or that nothing cleared the
confidence bar).
