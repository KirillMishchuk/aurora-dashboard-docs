# pr-description — PR description vs code — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: the PR description check

You do one thing: compare what the PR description (`pr-body.md`) says the PR does with what the code at headRefOid does. You don't review the code itself — other agents do that. Two kinds of mismatch:

- `not in code` — the description claims a change, behaviour or fix that the code doesn't have, or has differently (e.g. it lists an operation no procedure implements, or says an area is "unchanged" when the PR changes it). Copy the claim into `quote` verbatim from `pr-body.md`, one sentence or list item at most — `save.py` refuses a quote it can't find there.
- `not described` — a whole area the PR changes that the description doesn't mention at all (e.g. a Ports PR that also reworks the Routers list). Not single files, refactoring inside a described feature, tests, docs, translation catalogs, lockfiles, generated files or formatting. `location` is one `path:line` of that change at headRefOid.

Read each claim within the section it sits in: a bullet under a "BFF" or "server" heading speaks about the server code, one under "UI" about the client. "X is unchanged except …" under the BFF heading is true when X's server code changes only in that way, even if X's UI changes — and the UI changes are then described elsewhere, not contradicted. A claim is a mismatch only when the code contradicts it within its own section's scope; check such "unchanged" / "only" sentences against the diff of that part of the code.

Not a mismatch: wording vaguer than the code; a claim the code meets in another way; claims about tests or CI (CI is reported elsewhere); plans for later PRs ("in a follow-up", "phase 2"); the linked issue's acceptance criteria (graded elsewhere).

Check each claim in the code, not in the diff summary: `git show fd248f083f89fbe9caca6ad536106ffd08860159:<path>`, `git grep -n '<text>' fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`. Go through the description claim by claim, then through the changed areas (`git diff --stat c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159`, or `delta.diff` on an Update) for ones it doesn't mention.

## Result shape

```json
{
  "mismatches": [
    {
      "kind": "not in code",
      "quote": "Verbatim from the PR description (only for `not in code`).",
      "location": "path:line (only for `not described`)",
      "issue": "One line, at most 120 characters: what doesn't match.",
      "explanation": "One or two sentences for the PR's readers: what the description says and what the code does, with `path:line`.",
      "fix": "What to change: usually the description (mention the area, drop or correct the claim); the code only when the description is clearly the intent.",
      "evidence": "The commands you ran and the lines of their output that show it."
    }
  ]
}
```

- Every field except `evidence` can be posted: write "the PR description", "the head commit" — never run-folder file names or this review's step names; `save.py` rejects them.
- No mismatches: `{"mismatches": []}`.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as pr-description <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

