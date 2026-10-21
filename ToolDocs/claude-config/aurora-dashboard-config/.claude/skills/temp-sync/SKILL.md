---
name: temp-sync
description: >-
  Snapshot the currently git-staged files in this repo into two scratch
  subfolders of ../DOCS/transfer (one level above the repo root):
  ../DOCS/transfer/temp-files (the files themselves, preserving their relative
  directory hierarchy) and ../DOCS/transfer/patch (the same change set as a
  single `git diff --cached --binary` patch, for carrying uncommitted work to
  another machine). Both subfolders are cleared first every run, since each holds only the branch/PR
  currently in flight, not an accumulating pile from past ones. Then write the
  PR description for that same change set to ../DOCS/pr-descriptions/ — a third,
  accumulating folder that is never cleared. Use this whenever the user asks to
  copy/sync/snapshot staged files into temp-files, export the current staged
  changes for review elsewhere, make a patch of the current changes, move work
  to another machine, refresh either scratch folder, or write/update the PR
  description for the current change set — including phrasing like "скопируй
  застейдженные файлы", "обнови temp-files", "сложи текущие staged файлы в
  DOCS", "сделай патч текущих изменений", "перенести работу на другую машину",
  "напиши описание PR", or "добавь description".
---

# Sync staged changes to transfer/ (temp-files, patch) and pr-descriptions

Three folders under `DOCS/` (see the map in `DOCS/README.md`), all fed from
the same source of truth — the git index. The first two live together under
`DOCS/transfer/`, the folder that carries work to another machine
(`DOCS/transfer/README.md` describes the layout):

- **`DOCS/transfer/temp-files/`** — the staged files themselves, at their original
  relative paths. For handing a clean snapshot of in-progress changes to
  something outside the repo (another tool, a reviewer, an upload) without
  dragging along unrelated history.
- **`DOCS/transfer/patch/`** — the same change set as one `git diff --cached
  --binary` patch, named `<id>-on-<base-sha>.patch`. This is the transport
  between machines: `DOCS` is its own git repository, so the patch travels by
  commit and push, and is applied on the other side with `git apply`.
- **`DOCS/pr-descriptions/`** — the PR description for that same change set, as
  `pr-<number>-description.md` once a PR number exists, otherwise
  `pr-<kebab-slug>-description.md`. The user opens PRs themselves, so this is
  the text they paste into GitHub; it is written here rather than posted.

The first two are disposable and reflect *only* what's staged *right now*, so
neither is additive — leftovers from a previous sync would misrepresent the
current state, and clearing first is not optional. Each script clears only its
own subfolder, never `DOCS/transfer/` itself. `DOCS/transfer/patch/README.md`
is the single exception: it documents how to apply a patch and outlives any one
patch. `DOCS/transfer/README.md` sits outside both subfolders and is never
touched by the scripts.

**`DOCS/pr-descriptions/` is the opposite: it accumulates and is never cleared.**
One file per PR, kept after the PR merges. Rewrite the file for the current
change set; never delete the others.

## Steps

1. Run both bundled scripts from anywhere inside the repo, no arguments, no
   questions asked — this skill is meant to be invoked and just do its job:

   ```bash
   bash .claude/skills/temp-sync/scripts/sync_staged_to_tempfiles.sh
   bash .claude/skills/temp-sync/scripts/sync_patch_to_transfer.sh
   ```

   Each resolves the repo root and its own destination itself, and each
   refuses to run if the resolved destination doesn't end in the folder it
   expects — a safety check before a recursive delete.

   `sync_staged_to_tempfiles.sh` empties `DOCS/transfer/temp-files`, then copies every
   staged file that still exists on disk to its original relative path,
   skipping staged paths that no longer exist (staged deletions, or the old
   side of a rename) — there's nothing to copy for those.

   `sync_patch_to_transfer.sh` empties `DOCS/transfer/patch` except `README.md`,
   derives the patch name from the branch (an `issue-<n>` segment, else a
   trailing `-<n>`, else the branch slug without the `kiryl-` prefix) and the
   short SHA of `HEAD`, writes `git diff --cached --binary` there, and
   rewrites the `## Patches` table in `README.md` down to that one patch. Unlike
   the file mirror, the patch does carry deletions, renames and file modes.

2. **Fill in the table's description.** The script can only write facts it can
   read from git — branch and file count. Replace the `Contents` cell of
   that one row with a real one-sentence summary in English, in the style of
   the rows already there: branch, issue number, what the change actually
   does, file count. That column is the only thing telling the other machine
   what it's about to apply.

3. **Write the PR description** to `DOCS/pr-descriptions/`. Resolve the folder
   from the repo root, never as a bare `../DOCS` typed from a subdirectory —
   on macOS's case-insensitive filesystem that folds into this repo's own
   git-tracked `docs/` and ships in the next upstream PR:

   ```bash
   DESCRIPTIONS_DIR="$(dirname "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")/DOCS/pr-descriptions"
   ```

   The common git dir (not `--show-toplevel`) keeps this right from a linked
   worktree too: a worktree's toplevel sits under `.claude/worktrees/`, so its
   dirname is not the folder that holds `DOCS/`. The two sync scripts resolve
   their destinations the same way.

   The shape is **`.github/pull_request_template.md`** — this file is pasted
   into GitHub as the PR body, so it follows the template's level-1 headings
   (`# Summary`, `# Changes Made`, `# Related Issues`, `# Testing
   Instructions`, `# Checklist`), not a shape of your own. Read the staged
   diff (`git diff --cached`) and, as the style reference,
   `pr-1331-description.md` and `pr-1335-description.md`
   in that folder — they are what a good one looks like here.

   - `# Summary` — what the change does and *why*. If it came from a user
     report, quote it. Then one bolded paragraph per part of the root cause
     (`**Why the search box unmounts.**`, `**Why it flickers.**`), each with
     real `file.ts:line` citations, each explaining a mechanism rather than
     restating the diff. Name the commit/PR a regression came from.
   - `# Changes Made` — `## <area>` subsections (`## Server`, `## Client`,
     `## Types` — whatever the change actually spans). Bullets name the
     actual file, function or component and say what it does and why. No
     `## Tests` subsection: suite numbers and green checks don't go in the
     description.
   - `# Related Issues` — always present. `Fixes #N` when the issue number is
     known (branch name, the `Opened as #N` line in the matching `DOCS/issues/` draft,
     the PR's linked issues); otherwise
     `Fixes #` for the user to fill in, and say so in the report.
   - `# Testing Instructions` — `pnpm i`, `pnpm run test`, then the manual
     scenario, written so someone else can follow it.
   - `# Checklist` — the template's items, all `- [x]`.

   Add a section outside the template only when a reviewer would otherwise
   stumble, and give it a specific title the way the existing files do
   (`# Note on #1330`, `# Behaviour and Contract Changes`, `# Deliberately out
   of scope`) — for a change that reads like a revert of someone's recent PR,
   a field left in place that looks dead, or a narrowed contract.

   **Never do these:**

   - **No attribution line, and no mention of Claude, AI or generation
     anywhere in the file.** This is the user's PR body in their own voice.
   - **No `Not changed` section.**
   - **Don't mention changesets** — neither that one was added nor that none
     was needed.
   - Don't describe behaviour you have not read in the staged diff, and don't
     promise follow-up work: a deferred item belongs in `DOCS/FOLLOW-UPS.md`
     with a reference to its number, per that file's own rules.

   If a description for this same change set is already there, rewrite it in
   place rather than adding a second file.

   Start the file with a frontmatter block (it is for the Obsidian vault and
   is not part of what gets pasted into GitHub):

   ```markdown
   ---
   type: pr-description
   date: <today, YYYY-MM-DD>
   pr: [<number>]       # omit the line until the PR exists
   issue: [<number>]    # the issue in `# Related Issues`; omit if none
   ---
   ```

   When rewriting an existing file, keep its frontmatter and update only
   `pr`/`issue` if they became known. Then run
   `python3 "$(dirname "$DESCRIPTIONS_DIR")/tools/update-related.py"` to
   refresh the vault's "Related" links (skip silently if the script is missing).

4. Relay all three outputs to the user — including the path of the description
   file, since that one is the deliverable they act on. Four things are worth
   repeating rather than burying:

   - **Untracked files not in the patch.** The script warns when
     `git ls-files --others --exclude-standard` is non-empty. These are
     invisible to `git diff --cached`, so a patch missing them applies
     cleanly on the other machine and leaves a branch that doesn't build.
     If any of them look like branch work rather than scratch files, say so
     and suggest `git add -A` before re-running.
   - **Nothing staged.** Say so plainly — both scratch folders are now empty
     and no patch was written. An empty index is a valid state, not a failure.
     Skip step 3 entirely in that case: there is no change set to describe, and
     inventing one from the unstaged working tree would describe work the patch
     doesn't carry.
   - **Copy without the properties block.** Remind the user that the
     description file starts with a frontmatter block; only the text below
     the second `---` line goes into the GitHub PR body.
   - **What the description does not cover.** If the change set spans more than
     what's staged (say the user staged one of two related fixes), the
     description covers the staged half only — name that limit rather than
     letting them paste a description that overpromises.

5. Do not commit or push `DOCS`, and do not open a PR or post anything to
   GitHub. Writing the files is where this skill stops; the user commits and
   pushes the patch, and opens the PR with the description, themselves.

6. If either script refuses to run (destination path guard tripped), don't
   work around the check — tell the user what path it resolved to and let
   them confirm the repo layout is what they expect before retrying.

## Applying on the other machine

`DOCS/transfer/patch/README.md` carries the recipe. The short version, and the one
detail worth not getting wrong:

```bash
git checkout <base from the patch name>
git apply --index <patch>
```

`--index` matters for a round trip: plain `git apply` leaves everything
unstaged, so running this skill *there* would produce an empty patch and lose
the way back.
