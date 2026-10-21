#!/usr/bin/env bash
# Writes the current staged changes as a single git patch into ../DOCS/transfer/patch
# (relative to the repo root), for carrying uncommitted work to another machine.
#
# Same source of truth as sync_staged_to_tempfiles.sh — the index — so the file
# mirror and the patch can never describe different things. Unlike that mirror,
# the patch also carries deletions, renames and file modes, which a plain file
# copy cannot express.
#
# transfer/patch/ is cleared every run, like transfer/temp-files: it holds the
# branch in flight, not an archive. Only patch/ is touched — the sibling
# temp-files/ belongs to sync_staged_to_tempfiles.sh. README.md is the one exception — it documents how to apply a
# patch, and that outlives any individual patch.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
# DOCS/ sits next to the main checkout, not next to a linked worktree: from a
# worktree under .claude/worktrees/<name>, dirname of the toplevel would be
# .claude/worktrees. The common git dir is always <main checkout>/.git.
MAIN_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
DEST_DIR="$(dirname "$MAIN_ROOT")/DOCS/transfer/patch"

# Guard rail: the destination is about to be emptied, so refuse outright unless
# the resolved path really does end in DOCS/transfer/patch. Catches a missing sibling
# DOCS/ before it becomes a delete somewhere else.
case "$DEST_DIR" in
  */DOCS/transfer/patch) ;;
  *)
    echo "Refusing to run: resolved destination '$DEST_DIR' does not look like a DOCS/transfer/patch path." >&2
    exit 1
    ;;
esac

mkdir -p "$DEST_DIR"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
BASE_SHA="$(git rev-parse --short HEAD)"

# Patch identifier from the branch name. An issue number is what makes a patch
# recognisable at a glance, but branches spell it two ways here
# (kiryl-issue-1004-..., kiryl-storage-type-404-1081), so try both before
# falling back to the branch itself.
PATCH_ID="$(printf '%s' "$BRANCH" | sed -n 's/.*issue-\([0-9][0-9]*\).*/\1/p')"
if [ -z "$PATCH_ID" ]; then
  PATCH_ID="$(printf '%s' "$BRANCH" | sed -n 's/.*-\([0-9][0-9]*\)$/\1/p')"
fi
if [ -z "$PATCH_ID" ]; then
  # No number anywhere — use the branch slug, minus the personal prefix.
  PATCH_ID="$(printf '%s' "$BRANCH" | sed 's#^kiryl-##; s#[/ ]#-#g')"
fi

PATCH_NAME="$PATCH_ID-on-$BASE_SHA.patch"
PATCH_PATH="$DEST_DIR/$PATCH_NAME"

# Clear existing contents (mandatory every run), keeping only README.md.
cleared_count=0
while IFS= read -r entry; do
  [ -z "$entry" ] && continue
  [ "$(basename "$entry")" = "README.md" ] && continue
  rm -rf "$entry"
  cleared_count=$((cleared_count + 1))
done < <(find "$DEST_DIR" -mindepth 1 -maxdepth 1)

staged_count="$(cd "$REPO_ROOT" && git diff --name-only --cached | wc -l | tr -d ' ')"

# Untracked files that were never staged are invisible to `git diff --cached`.
# A patch missing them still applies cleanly on the other machine and leaves a
# branch that doesn't build, so surface them rather than let the success be
# quiet. Not an error: ignoring a scratch file is a legitimate choice.
unstaged_untracked=()
while IFS= read -r line; do
  [ -n "$line" ] && unstaged_untracked+=("$line")
done < <(cd "$REPO_ROOT" && git ls-files --others --exclude-standard)

echo "Destination: $DEST_DIR"
echo "Branch:      $BRANCH"
echo "Base:        $BASE_SHA"
echo "Cleared:     $cleared_count entr$([ "$cleared_count" = "1" ] && echo y || echo ies) (README.md kept)"

if [ "$staged_count" -eq 0 ]; then
  echo "Staged:      0 files — no patch written, transfer/patch/ is now empty."
else
  (cd "$REPO_ROOT" && git diff --cached --binary) > "$PATCH_PATH"
  patch_bytes="$(wc -c < "$PATCH_PATH" | tr -d ' ')"
  echo "Staged:      $staged_count file(s)"
  echo "Wrote:       $PATCH_NAME ($patch_bytes bytes)"
fi

if [ "${#unstaged_untracked[@]}" -gt 0 ]; then
  echo
  echo "WARNING: ${#unstaged_untracked[@]} untracked file(s) are NOT in the patch (never staged):"
  for f in "${unstaged_untracked[@]}"; do
    echo "  ? $f"
  done
  echo "  If any of these belong to the branch, run 'git add -A' and re-run —"
  echo "  the patch would otherwise apply cleanly and still not build."
fi

# Rewrite the README table down to the single patch that now exists. Everything
# above the table (purpose, git apply recipe) is left untouched.
README="$DEST_DIR/README.md"
if [ -f "$README" ] && grep -q '^| --- | --- | --- |$' "$README"; then
  if [ "$staged_count" -eq 0 ]; then
    row=""
  else
    row="| \`$PATCH_NAME\` | \`$BASE_SHA\` | Branch \`$BRANCH\`. $staged_count file(s). |"
  fi
  awk -v row="$row" '
    { print }
    /^\| --- \| --- \| --- \|$/ && !done {
      if (row != "") print row
      done = 1
      exit
    }
  ' "$README" > "$README.tmp"
  mv "$README.tmp" "$README"
  echo
  echo "README.md table rewritten to $([ "$staged_count" -eq 0 ] && echo "no rows" || echo "1 row")."
fi
