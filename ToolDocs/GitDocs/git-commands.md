---
type: tool-notes
---
# Git commands — practical reference

A list of git commands by category, for everyday work (not plumbing/git internals — objects, refs and `cat-file`/`hash-object` are not covered here). The focus is on what is actually used in practice, not the full `git` man page.

> Compiled 2026-08-20. Check current syntax with `git help <command>` or `git <command> --help`.

## Setup and repository creation

| Command | Description |
| --- | --- |
| `git init` | Creates a new git repository in the current folder. |
| `git clone <url> [dir]` | Clones a remote repository in full (history + all branches, unless specified otherwise). |
| `git clone --filter=blob:none <url>` | "Partial" clone — downloads the commit history without file contents, which are fetched on demand; faster for large repos if you don't need the whole working tree right away. |
| `git clone --depth 1 <url>` | Shallow clone — only the latest commit, no history. Fast, but `git log`/`git blame` are limited. |
| `git config user.name "..."` / `git config user.email "..."` | Commit author name/email for the current repository (without `--global` — for this repository only). |
| `git config --global user.name "..."` / `--global user.email "..."` | Same, but globally for all of the user's repositories. |
| `git config --list` | Shows all effective settings (global + local). |
| `git remote add origin <url>` | Links a remote repository under the name `origin`. |
| `git remote -v` | Lists remote repositories and their URLs (fetch/push). |

## Basic workflow: status, add, commit

| Command | Description |
| --- | --- |
| `git status` | What is modified, what is staged, what is untracked. |
| `git status --short` (`-s`) | Compact status output (`M`/`A`/`??` etc.). |
| `git add <file>` | Adds a file to the index (staging area) for the next commit. |
| `git add -p` | Interactively stages changes piece by piece (by hunks) instead of the whole file. |
| `git add -A` / `git add .` | Stages all changes — use with care, it's easy to accidentally commit something unwanted (secrets, junk files). |
| `git commit -m "message"` | Commits the staged changes. |
| `git commit -am "message"` | Commits all modified (but not new/untracked) files, skipping an explicit `git add`. |
| `git commit --amend` | Modifies the last commit (message and/or staged changes) — **don't do this after `push`** to a shared branch unless truly necessary (it rewrites history). |
| `git diff` | Diff of unstaged changes in the working directory. |
| `git diff --staged` (`--cached`) | Diff of what is already staged and will go into the next commit. |
| `git diff <file1> <file2>` | Diff of two specific files/commits/branches. |
| `git mv <from> <to>` | Renames/moves a file while preserving history — equivalent to `mv` + `git add`. |
| `git rm <file>` | Removes a file from the working directory and the index. |
| `git rm --cached <file>` | Stops tracking a file but keeps it on disk (e.g., you forgot to add it to `.gitignore`). |

## Branches

| Command | Description |
| --- | --- |
| `git branch` | Lists local branches; the current one is marked with `*`. |
| `git branch -a` | Lists all branches, including remote ones (`remotes/origin/...`). |
| `git branch <name>` | Creates a new branch from the current commit (does not switch to it). |
| `git branch -d <name>` | Deletes a local branch (only if it has already been merged). |
| `git branch -D <name>` | Force-deletes a local branch, even if it is not merged. |
| `git checkout <branch>` | Switches to an existing branch. |
| `git checkout -b <new-branch>` | Creates a new branch and immediately switches to it. |
| `git switch <branch>` | Modern equivalent of `git checkout <branch>` — only switches branches, with no side effects on files. |
| `git switch -c <new-branch>` | Equivalent of `git checkout -b` — create and switch. |
| `git merge <branch>` | Merges the specified branch into the current one. |
| `git merge --no-ff <branch>` | Merges with an explicit merge commit even if a fast-forward is possible — preserves in history the fact that there was a separate branch. |
| `git branch --merged` / `--no-merged` | Which branches are already merged into the current one / not yet merged — handy for cleanup. |

## Rebase

| Command | Description |
| --- | --- |
| `git rebase <branch>` | Moves the current branch's commits on top of the specified one — rewrites history (new commit hashes). |
| `git rebase -i <commit>` (interactive) | Interactive history rewriting — `reword`/`squash`/`drop`/reorder commits. |
| `git rebase --continue` | Continues a rebase after resolving a conflict. |
| `git rebase --abort` | Cancels a rebase and returns to the state before it started. |
| `git pull --rebase` | Like `git pull`, but replays your commits on top of the fetched ones instead of creating a merge commit. |

> Safety rule: don't rebase a branch that has already been pushed and that others are working on — history gets rewritten and will diverge from everyone else's local copies.

## Syncing with the remote repository

| Command | Description |
| --- | --- |
| `git fetch` | Downloads new commits/branches from the remote repository, but doesn't touch the working directory/current branch. |
| `git fetch origin refs/pull/<n>/head:<local-branch>` | Fetches a specific GitHub PR by number into a local branch without the `gh` CLI. |
| `git pull` | `fetch` + `merge` (or `rebase`, if configured) of the current branch with its upstream. |
| `git push` | Pushes the current branch's commits to its upstream. |
| `git push -u origin <branch>` | First push of a new branch — sets the upstream, after which a plain `git push` is enough. |
| `git push --force-with-lease` | A force push that is rejected if the remote has gained someone else's commits that you don't have (safer than a plain `--force`). |
| `git push --force` | Unconditional force push — overwrites the remote branch as is; dangerous on shared branches. |

**HTTPS authentication:** since 2021, GitHub no longer accepts a regular account password for git operations over HTTPS — you need a Personal Access Token in the password field (or an SSH key instead of HTTPS). This also applies to GUI clients (e.g., Fork) — if the client is set to "simple login" (username+password), you still need to paste a PAT there, not your real password. For organizations with SAML SSO (such as `cobaltcore-dev`), the token must additionally be authorized for the specific organization via "Configure SSO" on the token's page in GitHub settings.

## History and inspection

| Command | Description |
| --- | --- |
| `git log` | Commit history of the current branch. |
| `git log --oneline` | One line per commit (short hash + message). |
| `git log --oneline --graph --all` | Same + an ASCII graph of branches and merges across all branches. |
| `git log -p <file>` | Commit history with diffs affecting a specific file. |
| `git log --follow <file>` | File history including renames (`git mv`). |
| `git show <commit>` | Full information about a commit: metadata + diff. |
| `git blame <file>` | Who last changed each line of a file, and in which commit. |
| `git grep <pattern>` | Searches text in files tracked by git (in the tracked version, not blindly across the working directory). |
| `git diff <commit1>..<commit2>` | Diff between any two commits/branches/tags. |

## Undoing changes

| Command | Description |
| --- | --- |
| `git restore <file>` | Reverts a file in the working directory to the version from the index/last commit (modern equivalent of `git checkout -- <file>`). |
| `git restore --staged <file>` | Removes a file from the index (unstage) without touching changes in the working directory. |
| `git reset <file>` | Same as `restore --staged` — the old syntax. |
| `git reset --soft <commit>` | Moves the current branch to the specified commit, keeping all changes staged. |
| `git reset --mixed <commit>` (default) | Same, but the changes stay in the working directory, unstaged. |
| `git reset --hard <commit>` | Fully resets the branch and working directory to the commit — **irreversibly loses uncommitted changes**. |
| `git revert <commit>` | Creates a new commit that undoes the changes of the specified one — safe for already pushed/shared history (unlike `reset`). |
| `git clean -n` | Shows which untracked files `git clean` would delete (dry run, deletes nothing). |
| `git clean -fd` | Deletes untracked files and folders — no backup, use after `-n`. |

## Stash (temporarily shelving changes)

| Command | Description |
| --- | --- |
| `git stash` | Moves uncommitted changes to temporary storage; the working directory becomes clean. |
| `git stash -u` | Same, including untracked files. |
| `git stash list` | Lists saved stashes. |
| `git stash pop` | Restores the latest stash and removes it from the list. |
| `git stash apply` | Restores the latest stash but keeps it in the list (can be applied again elsewhere). |
| `git stash drop` | Removes a stash from the list without applying it. |

## Tags

| Command | Description |
| --- | --- |
| `git tag` | Lists tags in the repository. |
| `git tag <name>` | Creates a lightweight tag on the current commit. |
| `git tag -a <name> -m "message"` | Creates an annotated tag (with author/date/message — recommended for releases). |
| `git push origin <tag>` | Pushes a specific tag to the remote repository (tags are not pushed with a regular `git push`). |
| `git push origin --tags` | Pushes all local tags. |
| `git checkout <tag>` | Switches to the commit pinned by the tag (detached HEAD — not a branch). |

## Conflict diagnostics and troubleshooting

| Command | Description |
| --- | --- |
| `git status` (during a conflict) | Shows which files are in conflict and what is already resolved. |
| `git diff` (during a conflict) | Shows the conflict markers (`<<<<<<<`/`=======`/`>>>>>>>`) in context. |
| `git merge --abort` | Cancels a merge and returns to the state before it started. |
| `git bisect start` / `bisect good` / `bisect bad` / `bisect reset` | Binary search for the commit that introduced a bug, between a known "good" and "bad" commit. |
| `git reflog` | History of `HEAD` movements (including `reset --hard`, rebase, deleted branches) — a way to find a "lost" commit if it hasn't been garbage-collected yet. |

---
Updated: 2026-08-20
