# texts.json and findings.json — review-and-comment-pr

## Contents

- texts.json — what you write (top of this file)
- findings.json — what assemble.py builds
- Shape
- Fields
- Code and line citations
- Text rules
- Running it

Read this at Step 6. You write `<run folder>/texts.json` — the wording.
`assemble.py --texts` combines it with the scorers' and the describer's
results into `findings.json`, and `render.py` turns that into the report.
The template is at the end of `compose.md`:

- `summary`, `confidence` (`High` | `Medium` | `Low`), `index_affected`;
- `findings`: per id from `compose.md`, `issue`, `title`, `explanation`,
  `fix` (rules below under "Fields");
- `edge_cases`: extra QA edge cases, e.g. the scenario behind each Bug;
- `merge`: `{"<drop id>": "<keep id>"}` for a look-alike pair that is one
  problem;
- on an Update only: `earlier` (plus `confidence`) instead of `summary`,
  `index_affected` and `edge_cases` (the Update block has no QA plan:
  `edge_cases` given there are dropped) — one entry per finding of the
  existing report, `{"CR2": {"status": "fixed" | "partly" | "open" | "dropped",
  "note": "one line: what changed or what's left"}}`. The template in
  `compose.md` comes filled from the `earlier-findings` agent, which checked each at
  the new head; render.py refuses a list with one left out or one that
  isn't in the report.
- `fixes`: exact replacements after the fact-check, copied from
  `out/factcheck.json`, `{"field": "overview.how", "old": "…", "new": "…"}`
  (`overview.what|how|affects`, `qa.core_path[i]`, `qa.edge_cases[i]` —
  indices as in `findings.json` — or `findings.<id>.issue|title|explanation|fix|location`);
  also the way to fix an error render.py reports in the describer's text;
- optional `process`, `process_overrides`, `provenance_extra` — as below.

The rest of this file describes `findings.json` — what assemble.py
writes and render.py checks; its rules for the text fields apply to what
you write in `texts.json`.


## findings.json

`assemble.py --texts` writes it; on a release PR you write it yourself
(Step 2), with every required key: `schema_version`, `summary`,
`confidence`, `findings` (each with `score`, `severity`, `category`,
`issue`, `location`, `title`, `explanation`, `fix`), `overview.what`,
`qa.edge_cases` (not empty) and `index_affected`. `scripts/render.py`
turns it into the report, the index row and the footer. Layout,
numbering, verdict, header, footer, tables, Process defaults and the
index are code: don't write them. `dismissed` (the candidates scored
below 50, for the report's "Checked and dismissed" section; those whose
`discussion` cites a review comment also go into the posted "Review
comments not taken up") is written by assemble.py too; leave it out on a
release PR.

## Shape

```json
{
  "schema_version": 1,
  "summary": "2–4 sentences: the overall shape, the one or two things that matter, what clears it. Say here if CI/security fell back or acceptance couldn't be verified.",
  "confidence": "Medium",
  "findings": [
    {
      "id": "project-id-filter",
      "score": 75,
      "severity": "Major",
      "category": "Bug",
      "issue": "`list` sends `project_id` to Neutron, so shared networks are hidden",
      "location": "packages/aurora/src/server/Network/routers/networksRouter.ts:39",
      "precedent": null,
      "title": "`list` filters by `project_id`, hiding shared and external networks",
      "explanation": "What's wrong, where, what it leads to — Markdown, excerpts allowed.",
      "fix": "One or two sentences; a code block only when it clarifies."
    }
  ],
  "process": [],
  "process_overrides": {},
  "overview": { "what": "…", "how": "…", "affects": "…" },
  "qa": { "core_path": ["…"], "edge_cases": ["…"] },
  "provenance_extra": [],
  "index_affected": "The touched surface — procedures, routes, components, public exports."
}
```

## Fields

- **`findings`** — every scored issue with score **50, 75 or 100**; leave
  out everything scored 0 or 25. render.py sorts by severity and puts
  🔴 Critical / 🟠 Major / 🟡 Moderate into Required Changes (`CR1…`) and
  🟢 Low / ⚪ Trivial into Improvements (`I1…`).
  - `severity`: `Critical`, `Major`, `Moderate`, `Low` or `Trivial`.
  - `category`: exactly one of `Bug`, `Security`, `Accessibility`, `UI/UX`,
    `Code Quality`, `Performance`, `Docs`, `Test coverage`.
  - `issue`: the table cell — one line, about 120 characters at most.
  - `title`: the bold heading in "Explanation & Fix" — one line.
  - `location`: a full repo-relative `path:line` or `path:from-to` that
    exists at `<headRefOid>` (render.py checks it), or one of `PR state`,
    `PR body`, `PR files`, `CI`. Never shortened with `…/`.
  - `precedent`: the scorer's tag, copied by assemble.py — `null`,
    `{"kind": "existing", "ref": "<path:line at baseRefOid>"}` (same
    pattern in merged code) or `{"kind": "deferred", "ref": "<GitHub
    URL>"}` (a maintainer accepted or postponed it). render.py shows it as
    the Precedent column and a `_Precedent:_` line; optional on a release PR.
  - `explanation`: start with what the user or the system gets from it —
    a concrete case and when it happens (the candidate's claim has it);
    then where in the code; the rule (B.<n>, an API reference with its
    link) comes last, as support, not as the reason. If the review
    discussion raised it, who, where and what happened. A code block only
    when it shows the problem itself; a single line goes inline as code.
    The precedent is rendered from `precedent` — don't repeat it. Fold "no
    test covers this" in here instead of a separate finding.
  - `fix`: one or two sentences: what to change, and the code to copy —
    the `example:` from the evidence (`path:line`) when there is one.
  - `id` (optional): a short slug (`a-z`, `0-9`, `-`), needed only when
    another text refers to this finding.
- **`process`** — Process items you add yourself (rare): `issue`,
  `location`, `title`, `explanation`, `fix`, optional `id`. No score,
  severity or category. Mismatches between the PR description and the
  code come from the `pr-description` agent as `desc-1`, `desc-2` … —
  assemble.py puts them in as written.
  Unlinked issue and missing changeset come from `context.json`
  `process` with a standard text — don't repeat them here.
- **`process_overrides`** (optional) — replace any of `title`, `issue`,
  `location`, `explanation`, `fix` of a Process item from `context.json`,
  keyed by its id (`no-linked-issue`, `missing-changeset`, and `desc-<n>`
  from the `pr-description` agent — assemble.py applies those itself).
- **`confidence`** — `High`, `Medium` or `Low`: how sure you are the PR is
  sound once the Required Changes are cleared. Lower it for anything you
  could not verify (CI unreadable, acceptance not checkable,
  security-reviewer fallback used). Draft state doesn't count.
- **`acceptance`** from `describer.json` doesn't go into findings.json: unmet criteria become findings, and the grading is mentioned in `summary`.
- **`overview`** — the three Solution Overview folds, Markdown: `what`
  (the story of the change by area; a failing CI goes here), `how`
  (walkthrough with verbatim excerpts and `file:line` citations at
  `<headRefOid>`), `affects` (consumers, contract changes, anything left
  inconsistent). On a release PR only `what`.
- **`qa`** — `core_path`: numbered steps without the numbers; `edge_cases`:
  bullets without the `- `, each with `file:line` where it comes from a
  branch in the code, plus the scenario behind every Bug finding. On a
  release PR only `edge_cases`.
- **`provenance_extra`** — footer notes beyond `context.json` `provenance`,
  e.g. `security-reviewer fallback used`.
- **`index_affected`** — at most ~40 words, no verdict (render.py appends
  it).
- **`scope`** (optional) — one short line naming the epic/issue and the
  part this PR delivers (`#816 — Phase 1, read-only`), shown after "Must
  fix before merge". assemble.py takes the describer's; put `scope` in
  texts.json only to correct it (`null` drops it).

## Code and line citations

| Write | render.py puts in |
| --- | --- |
| `[[code:<path>:<from>-<to>]]` (own line) | those lines at `<headRefOid>` as a fenced block, indentation trimmed |
| `[[code:<path> \| <text> \| <n>]]` (own line) | `n` lines from the one line containing `<text>` |
| `[[at:<path> \| <text>]]` | `` `<path>:<line>` `` of the one line containing `<text>` |
| `[[at:<path>:<line>]]` or `` `<path>:<line>` `` | itself, after checking that the line exists |
| `location`: `<path> \| <text>` | `<path>:<line>` |

- `<text>` must be on exactly one line of the file; on 0 or several
  matches render.py lists the closest lines or the line numbers — make the
  text unique or give the number. Pick a distinctive piece of the line (a
  whole expression or string), not a bare identifier that also appears in
  imports or other uses.
- An excerpt is 30 lines at most; aim for 3–15.
- `[[code:…]]` goes in `explanation`, `fix` and `overview`; `[[at:…]]`
  anywhere.
- A code block you type yourself in `explanation` or `overview` must be
  verbatim at head or base. A first line `// <path>:<line>` is read as its
  caption and checked against that line. Command output, other PRs' code
  and pseudo-code go in a ```` ```text ```` block. Blocks in `fix` are
  proposals and aren't checked.
- A citation of a file that's not in this PR (e.g. another PR's file) is
  only a warning.

## Text rules

- **Refer to findings by id, never by number.** Numbers are assigned after
  sorting, so write `[[ref:<id>]]` — render.py replaces it with `CR2`,
  `I5`, `P1`…; Process items from `context.json` are referenced by their id
  (`[[ref:no-linked-issue]]`). A hard-coded `CR1` / `I3` / `P2` outside code is
  rejected. On an Update, the report's earlier findings are named by
  their number as plain text (`CR2 is fixed`), e.g. in an `earlier` note;
  the Update's own findings still go by `[[ref:<id>]]`, and
  Process items from `context.json` can't be referenced there.
- English, Markdown. Inline code that itself contains a backtick goes in a
  longer fence with spaces (`` t`Try Again` ``) — never `\``. HTML-like
  text goes inside backticks. Paths always in full.
- In JSON strings, newlines are `\n` and quotes `\"`; a fenced code block
  is fine inside `explanation`, `fix` and `overview`.

## Running it

```bash
python3 .claude/skills/review-and-comment-pr/scripts/render.py --run <run folder>
```

Exit 1 lists every problem by field (`findings.c12.location: …`): fix it
in `texts.json` — a finding's text directly, anything else (the describer's
text, a location) with a `fixes` entry — then run `assemble.py --texts` and
render.py again; on a release PR fix `findings.json` itself. Nothing
reaches `DOCS` until it passes. `--check` validates only; `--dry-run` writes `<run folder>/report.md`
without touching `DOCS`.
