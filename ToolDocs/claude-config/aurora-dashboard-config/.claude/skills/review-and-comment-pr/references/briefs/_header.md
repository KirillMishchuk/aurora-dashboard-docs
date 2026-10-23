# {{role}} — review-and-comment-pr, aurora-dashboard PR #{{number}}

- Run folder: `{{run}}` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`{{issue_files}}
- headRefOid: `{{head}}`
- baseRefOid: `{{base}}`
{{scope}}
Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff {{base}}...{{head}} -- <path>`.

Work in few, large steps: every tool call is a round trip that re-reads your whole context. Put independent commands into one Bash call, separating their output with `echo '--- <label>'`. Read a file you need once, whole and numbered — `git grep -n '' {{head}} -- <path> <path2> …` takes several paths in one call — instead of line range by line range or one `git blame` per line.

