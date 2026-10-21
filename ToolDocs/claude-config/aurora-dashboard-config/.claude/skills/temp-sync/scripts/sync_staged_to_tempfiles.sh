#!/usr/bin/env bash
# Mirrors currently git-staged files into ../DOCS/transfer/temp-files (relative to the
# repo root), preserving their relative directory hierarchy. Clears out
# whatever is already in temp-files first, every run — it's a disposable
# scratch mirror of "whatever's in flight right now", not an accumulating
# archive, so stale files from a previous branch/PR must never linger.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
# DOCS/ sits next to the main checkout, not next to a linked worktree: from a
# worktree under .claude/worktrees/<name>, dirname of the toplevel would be
# .claude/worktrees. The common git dir is always <main checkout>/.git.
MAIN_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
DEST_DIR="$(dirname "$MAIN_ROOT")/DOCS/transfer/temp-files"

# Guard rail: the destination is about to be recursively emptied, so refuse
# to run at all unless the resolved path really does end in DOCS/transfer/temp-files.
# This catches a misconfigured repo layout (e.g. no sibling DOCS/ folder)
# before it turns into a delete of the wrong directory.
case "$DEST_DIR" in
  */DOCS/transfer/temp-files) ;;
  *)
    echo "Refusing to run: resolved destination '$DEST_DIR' does not look like a DOCS/transfer/temp-files path." >&2
    exit 1
    ;;
esac

mkdir -p "$DEST_DIR"

# Clear existing contents (mandatory every run), but keep the directory itself.
cleared_count=$(find "$DEST_DIR" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')
find "$DEST_DIR" -mindepth 1 -delete

# Staged paths, relative to repo root. Includes deletions/renames as git
# reports them — filtered below by "does it still exist on disk".
# Built with a while-read loop (not `mapfile`) since macOS ships bash 3.2,
# which predates mapfile/readarray.
staged_files=()
while IFS= read -r line; do
  [ -n "$line" ] && staged_files+=("$line")
done < <(cd "$REPO_ROOT" && git diff --name-only --cached)

copied=()
skipped=()

for rel_path in "${staged_files[@]:-}"; do
  [ -z "$rel_path" ] && continue
  src="$REPO_ROOT/$rel_path"
  if [ -f "$src" ]; then
    dest="$DEST_DIR/$rel_path"
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    copied+=("$rel_path")
  else
    # Staged deletion, or a rename's old path — nothing on disk to copy.
    skipped+=("$rel_path")
  fi
done

echo "Destination: $DEST_DIR"
echo "Cleared: $cleared_count existing top-level entr$([ "$cleared_count" = "1" ] && echo y || echo ies)"
echo "Copied: ${#copied[@]} file(s)"
for f in "${copied[@]:-}"; do
  [ -n "$f" ] && echo "  + $f"
done
if [ "${#skipped[@]}" -gt 0 ]; then
  echo "Skipped (staged but not present on disk, e.g. deletions/renames): ${#skipped[@]}"
  for f in "${skipped[@]}"; do
    echo "  - $f"
  done
fi
if [ "${#staged_files[@]}" -eq 0 ]; then
  echo "No staged files found — temp-files is now empty."
fi
