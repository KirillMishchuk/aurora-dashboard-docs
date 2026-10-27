# review-and-comment-pr — regression check

Replays every scripted step of the skill on saved runs and compares the output with `golden/`.
No agents, no network, nothing written to DOCS. Run it before and after every change to the skill.

```bash
cd ~/projects/SAP/DOCS/ToolDocs/claude-config/review-pr-regression
python3 -B run.py --skill ~/projects/SAP/aurora-dashboard/.claude/skills/review-and-comment-pr \
                  --repo ~/projects/SAP/aurora-dashboard
```

- `OK` for every fixture — the change didn't alter any output.
- Differences are printed as unified diffs per file. An expected one (the change you meant to make):
  check it, then `--update` writes the new golden. An unexpected one is a regression.
- `--only <fixture>` runs one fixture.

## Fixtures

| Fixture | Mode | What it covers |
| --- | --- | --- |
| `1393-fd248f08` | full | 7 finders, 9 scorer batches, 32 findings, Copilot threads, "Review comments not taken up" |
| `1383-0a594e9e` | full | an older run: finder outputs without `example:`, render stops on the removed `Conflict` category |
| `1377-86a355a8` | update | 14 earlier findings incl. `dropped` (CR4), describer-update brief, verdict with Confidence |
| `1393-64c47a99` | update | author fixed findings (partly / fixed), a new finding replacing an earlier one, thread URLs in `discussion` |

Each fixture holds the run folder minus generated files (`briefs/`, `candidates.json`, `compose.md`,
`findings.json`, `report.md`, the diffs) and, for an Update, `report-before.md` — the KB report as it was
before that run. `{{SAP}}` stands for the SAP folder; the aurora-dashboard checkout must contain the
fixtures' commits.

A brief change that alters what an agent writes isn't covered by the saved `out/*.json`: add a
fixture (or edit one's `out/`) in the new format, so the scripts that read it are exercised too.
