# create-plan — regression check

Replays `aurora-dashboard/.claude/skills/create-plan/scripts/plan.py` on saved fixtures and compares the
output with `golden/`. No agents, no network, nothing written to the real DOCS or repo: each fixture runs
in a temp `SAP/` folder (DOCS copied from `docs-base/`, an empty `aurora-dashboard/`), and git, GitHub and
image downloads are answered from the fixture's `calls.json`. Run it before and after every change to the
script or to how the skill calls it.

```bash
cd ~/projects/SAP/DOCS/ToolDocs/claude-config/create-plan-regression
python3 -B run.py --skill ~/projects/SAP/aurora-dashboard/.claude/skills/create-plan
```

- `OK` for every fixture — the change didn't alter any output.
- Differences are printed as unified diffs per file. An expected one (the change you meant to make):
  check it, then `--update` writes the new golden. An unexpected one is a regression.
- `--only <fixture>` runs one fixture.

Golden per fixture: `log.txt` (every step: command, exit code, output), `docs.diff` (what the steps changed
in DOCS against `docs-base/`), `run/…` (the run folder: `task.md`, `context.json`, `github.md`, `plan.md`,
`written.json`).

## Fixtures

| Fixture | What it covers |
| --- | --- |
| `1387-issue-epic-image` | issue + parent epic + one image (download answered 200) → save → write → taken slug refused → followups: incomplete options refused, file into K + ref to 43, second run refused |
| `1208-behind-no-image` | working copy 2 commits behind `origin/main` (the C3 question), uncommitted changes, no epic (404), image not downloadable (listed as "not downloaded"); Base and `**Reviewed:**` in the header |
| `save-rejects` | `collect --text`; `write` before `save`; `save` refusing a Decisions block, absolute paths, a trailing file list, a broken structure (title, unknown section, missing section, step numbering, severity, follow-up fields), a missing run folder; `followups` before `write` |
| `fu-42-analysis` | follow-up item as the task (+ the "set it to done" note); a plan without steps → `status: analysis`; all candidates skipped |
| `pr-1398-not-mine` | someone else's PR → mode A; without `gh` the owner is unknown → exit 3, then `--not-mine`; closing issues from the PR body |
| `pr-1393-mode-b` | the user's own PR (`--mine`) → mode B: review sources (KB report, GitHub threads incl. outdated), no original plan → `write` refuses without `--original-plan`; round 1 (+ `pr:` added to the original plan, a follow-up into a new section N), round 2 appended with `--reviewed`, index row updated in place, follow-ups only in round 2 |

`calls.json` was recorded with `CREATE_PLAN_RECORD=<dir> plan.py collect …` (in a clone; without `gh`, so
GitHub came through unauthenticated `curl`), then edited by hand where a fixture needs another answer
(`download` → 200, `user` → null, `git status --porcelain`, `git rev-parse --short refs/remotes/origin/pr/1393`).
`{{MAIN}}` in it stands for the repo path. The planner's plans (`plan-*.md`, `decisions.md`) are real
`dev-planner` outputs from runs 1387-v1 and 1388-v1, plus a hand-made broken one.

To add a fixture: record `collect` into a new folder, add the answers the later steps need (`write` asks
git for the branch, short SHA, `status --porcelain` and the lag), write `steps.json`, run with `--update`
and read the new golden before trusting it.
