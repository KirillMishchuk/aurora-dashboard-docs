---
type: index
---
# transfer

Everything needed to carry uncommitted `aurora-dashboard` work to another machine. `DOCS` is its own git repository, so this folder travels by commit and push. On the other machine: pull `DOCS`, then apply the patch as described in [`patch/README.md`](./patch/README.md) — no scripts needed there. To send the work back, stage it and run `temp-sync` on that machine.

| Folder | What it holds | Written by |
| --- | --- | --- |
| [`patch/`](./patch/) | The staged change set as a single `git diff --cached --binary` patch, named `<id>-on-<base-sha>.patch`, plus `README.md` with the `git apply` recipe and a one-row table describing the current patch. The patch carries deletions, renames and file modes. | `temp-sync` skill (`sync_patch_to_transfer.sh`) |
| [`temp-files/`](./temp-files/) | The same staged files as plain copies at their original relative paths — for reading or copying individual files without applying the patch. Does not carry deletions or renames. | `temp-sync` skill (`sync_staged_to_tempfiles.sh`) |

Both subfolders hold only the change set currently in flight: each is emptied on every `temp-sync` run (except `patch/README.md`). This `README.md` sits outside them and is never touched by the scripts.

To apply the work on the other machine, follow [`patch/README.md`](./patch/README.md).
