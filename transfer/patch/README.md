---
type: index
---
# transfer/patch

Uncommitted `aurora-dashboard` changes travelling between machines through this repository.
Each file is a `git diff --cached --binary` taken from the working tree; its name contains the base commit.

## How to apply

```bash
cd <path to aurora-dashboard>
git fetch origin
git checkout <base from the patch name>      # e.g. 9775e4bb
git apply <path to DOCS>/transfer/patch/<file>.patch
```

Useful:

- `git apply --check <file>.patch` — check whether it applies, without changing anything.
- `git apply --index <file>.patch` — apply straight into the index (as it was on the source machine).
- `git apply --3way <file>.patch` — if the base has drifted: merge instead of refusing.

## Patches

| Patch | Base | Contents |
| --- | --- | --- |
| `security-groups-detail-page-on-505e3e1b.patch` | `505e3e1b` | Branch `kiryl-security-groups-detail-page`, PR #1375, on top of the PR commit: import order in `SecurityGroupTabs.tsx` (react → lingui → Juno, `import type { ReactNode }`) per a Copilot comment. 1 file. |
