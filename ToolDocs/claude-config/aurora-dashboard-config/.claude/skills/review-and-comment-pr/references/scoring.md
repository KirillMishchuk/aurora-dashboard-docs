# Scoring rules — review-and-comment-pr

Read all of this before scoring. The issues you get were found by other
agents; you didn't find them and must not take the finders' word for them.

## Verify first

For each issue, open the cited code with `git show <headRefOid>:<path>`,
re-run any command the evidence rests on, and check the claim before
scoring.

## Score

Use exactly one of 0, 25, 50, 75 or 100 — no values in between. When an
issue sits between two levels, pick one and say in the reason what kept it
from the other.

- **0**: not confident at all — false positive or pre-existing issue.
- **25**: might be real, might not; the scorer checked the code and still
  can't tell. If stylistic, not explicitly called out in the review
  standards.
- **50**: verified real, but a nitpick or rare in practice; not very
  important relative to the rest of the PR.
- **75**: highly confident — verified in the code, will likely be hit in
  practice, existing approach is insufficient, or a verified violation of
  a rule quoted from the review standards.
- **100**: absolutely certain, confirmed by direct evidence, will happen
  frequently.

## Rules that adjust the score

**Evidence rule.** When an issue quotes an official API reference or the
review standards, and the code at `<headRefOid>` does what the quote says
it must not, the issue is verified — score it on its impact (50, 75 or
100). "Can't run it" or "can't reach the docs" is never a reason for 25
when the quote and the code are in front of the scorer.

**Precedent-table rule.** When an issue matches a row of "Severity
precedents" below and the code at `<headRefOid>` does what the row
describes, the issue is verified: score it at least 50 and give it the
row's severity. How often it is hit in practice is already priced into
that severity — not a reason for 25.

**External-API claims.** When an issue rests on how OpenStack, Ceph or S3
behave, the scorer uses the doc quote agent f attached, or opens the
reference itself, reading it as `.claude/agents/external-api-checker.md`
describes — never its memory. "From memory" is no basis for 25 or for a
lower impact. A feature that silently leaves out data users expect to see
counts as "will likely be hit in practice".

**Quick Reject rule.** `copilot-instructions.md` has a "Quick Reject
Checklist" — violations the project says should stop a PR in review. The
scorer checks every issue against it, and a verified violation of a
checklist item scores at least 75, even when the same pattern already
exists elsewhere in the code: the project has ruled it out for new code.
Quote the checklist item in the reason. Its "What NOT to Review" scope
still wins (e.g. hardcoded strings in `packages/aurora` are lint-enforced,
not a finding).

**Precedent rule.** A maintainer declining the same change on another PR,
or the same pattern already existing elsewhere in the code, never lowers
the score of a verified issue — this PR adds new code, and the standards
apply to it. Put the precedent in the reason instead, so the reader knows
to expect pushback. (Lines this PR didn't touch are still "pre-existing"
and score low — see "Usual false positives".)

**Usual false positives** — give these 0–25, so they stay out of the
report (adapted from the list `code-review` uses): pre-existing issues;
things that look like bugs but aren't; pedantic nitpicks a senior engineer
wouldn't raise; anything a linter, typechecker or CI would catch; general
code-quality opinions (test coverage, docs, generic security hardening
such as "add rate limiting" with no concrete exploit path in this PR)
unless the review standards explicitly require them; issues explicitly
silenced in code (lint-ignore comments); intentional changes that are
clearly part of the broader PR; real issues on lines the PR didn't touch.

## Severity — for every issue scored 50 or more

Rate how bad it is if left in, independently of the score, on a five-level
scale with its marker:

- 🔴 **Critical**: breaks a core flow for all users, opens a security
  hole, or loses/corrupts data.
- 🟠 **Major**: breaks a feature or hides data users expect, with no easy
  workaround.
- 🟡 **Moderate**: noticeable but bounded — degraded UX, an accessibility
  gap, duplicate requests, a merge conflict with another open PR, a broken
  project rule with a visible effect.
- 🟢 **Low**: cosmetic, wording, a rule violation users rarely notice.
- ⚪ **Trivial**: a nit with no user-facing effect (import order, a
  contradicted JSDoc on a rarely-hit path).

Score and severity answer different questions: a Quick Reject violation
scores at least 75 but can be 🟢 Low. Issues scored 0 or 25 get no
severity.

### Severity precedents

Rate these common cases the same way every time; deviate only with a
concrete reason, and name it in the reason.

| Case | Severity |
| --- | --- |
| A list filter hides resources the service's default policy lets the user see | 🟠 Major |
| No pagination, and the reference gives a finite default page size | 🟡 Moderate |
| No pagination, and the API returns everything by default | 🟢 Low |
| The same data fetched twice (e.g. loader + `useQuery`) | 🟡 Moderate |
| `Conflict` — merge conflict with, or work duplicated in, another open PR | 🟡 Moderate |
| State the standards want in the URL (tab, filter) kept in `useState` | 🟢 Low |
| 401/403 handled inline instead of redirect / page-level message | 🟢 Low |
| Quick Reject UI rules (raw HTML element, all-caps, "Please", import order) | 🟢 Low or ⚪ Trivial |
| No tests for new code, when the epic or the standards require them (otherwise a usual false positive, 0–25) | 🟢 Low |
| An issue criterion inside the PR's stated scope only partly delivered (criteria outside it are marked `out of scope` and never reach you) | 🟢 Low |

## Category — for every issue scored 50 or more

Exactly one kind: `Bug`, `Security`, `Accessibility`, `UI/UX`,
`Code Quality`, `Performance`, `Docs`, `Test coverage`, or `Conflict`
(a merge conflict with `main` or another open PR — changesets included —
or the same work duplicated in another open PR). (Process items —
draft, description-vs-code mismatch, missing changeset, unlinked issue —
are tagged `Process`; they come from Steps 1–2, not the scorer.)

## What to return

For each issue: the score, the severity (score ≥50), the category, and a
one- or two-sentence reason naming what it checked and what it found
(file:line, quote, behaviour) and why that severity — the report shows
this reason in the finding's "Explanation & Fix".
