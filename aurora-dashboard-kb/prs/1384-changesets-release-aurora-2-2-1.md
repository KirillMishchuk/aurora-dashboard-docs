---
type: pr-report
date: 2026-10-17
status: open
pr: [1384]
issue: []
author: app/cobaltcore-bot
branch: changeset-release/main
---

# PR #1384: publish(npm): automate Package Versioning and Publishing with Changesets

**Author:** app/cobaltcore-bot · **Status:** open · **Base:** `main` ← `changeset-release/main`
**Size:** 6 files, +23 / −18 · **Created:** 2026-10-13 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1384)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **🟢 Approve with nits** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **High**

This is the automated Changesets release PR: it consumes the two pending patch changesets from #1379 and bumps `@cobaltcore-dev/aurora` from 2.2.0 to 2.2.1, plus the private `@cobaltcore-dev/dashboard` app from 1.2.17 to 1.2.18. The bump type matches the changesets, 2.2.1 is not on npm yet (latest is 2.2.0), the branch is based on the current `main` (`a21ba3e`), and all CI checks pass. The only nit is cosmetic: one changelog entry renders its first bullet inline after the commit hash. Three open draft PRs (#1377, #1385, #1386) each add a `minor` changeset for `@cobaltcore-dev/aurora`. If any of them lands before this PR merges, the bot will regenerate this PR as 2.3.0.

### 🔧 &nbsp; Required Changes

None.

### 💡 &nbsp; Improvements

| #   | Severity | Category | Issue                                                                    | Location                         |
| --- | -------- | -------- | ------------------------------------------------------------------------ | -------------------------------- |
| I1  | 🟢 Low   | Docs     | Changelog entry starts with `- a21ba3e: - …`, so its first bullet merges into the hash line | `packages/aurora/CHANGELOG.md:8` |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — List-only changeset renders a broken first bullet** · Docs · `packages/aurora/CHANGELOG.md:8`
`.changeset/fix-image-ux-improvements.md` has no summary line, only a bullet list. Changesets prefixes the body with `- a21ba3e: `, so line 8 reads `- a21ba3e: - Exclude pending/rejected shared images from All Images view`. In Markdown the inner `- ` is literal text: the first change is glued to the hash, and only the remaining six become a nested list. The same pattern already appears in ten older entries of this CHANGELOG (e.g. lines 84, 168, 376), so expect this to be treated as house style. It is cosmetic.
_Fix:_ Don't edit this branch, because the bot regenerates it. On `main`, give `.changeset/fix-image-ux-improvements.md` a one-line summary (e.g. `Image UX improvements:`) above the bullet list, and the bot will rewrite the entry.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

`changesets/action` generated this PR from `main` at `a21ba3e`, which is the merge of #1379, "fix image issues and inconsistencies from pre-release-review". It is a single commit, `aa157d0` (`chore(version): update versions with Changesets`). The PR changes no source code.

- **Consumed changesets.** It deletes `.changeset/fix-image-sharing.md` and `.changeset/fix-image-ux-improvements.md`. Both were `"@cobaltcore-dev/aurora": patch`. After the PR, `.changeset/` holds only `README.md` and `config.json`.
- **`@cobaltcore-dev/aurora` 2.2.0 → 2.2.1.** The PR bumps `packages/aurora/package.json` and adds a `## 2.2.1` → `### Patch Changes` section to `packages/aurora/CHANGELOG.md`, with both changeset bodies attributed to `a21ba3e`. Two patch changesets give a patch bump, and that is what the PR does. `npm view @cobaltcore-dev/aurora version` returns `2.2.0`, so 2.2.1 is free. No other commit has landed on `main` since the 2.2.0 release commit (`6a8dad6`), so the changelog covers every change since that release.
- **`@cobaltcore-dev/dashboard` 1.2.17 → 1.2.18.** The app is `"private": true` and depends on `"@cobaltcore-dev/aurora": "workspace:*"`. With `updateInternalDependencies: "patch"` in `.changeset/config.json`, Changesets bumps it as a dependent. Its changelog lists `Updated dependencies [a21ba3e]` twice (once per changeset), which is standard Changesets output. Nothing is published for it.
- **CI.** All checks pass on `aa157d0`: lint, type-check, test, build, format, check-i18n, licenses, CodeQL, DCO, PR-title validation and preview. The PR has no review comments.

</details>

---

## QA Test Plan

<details>
<summary><strong>Edge Cases</strong></summary>

- **A pending minor changeset lands first.** Draft PRs #1377 (`neutron-ports-management.md`), #1385 (`neutron-networks-management.md`) and #1386 (`networks-management-phase1.md`) each add `"@cobaltcore-dev/aurora": minor`. If one merges before this PR, the bot regenerates the PR as 2.3.0. Before you merge, check that the PR still says 2.2.1 and that its head is the commit you reviewed.
- **Version already taken.** Right before you merge, run `npm view @cobaltcore-dev/aurora version` again. If it shows 2.2.1, someone published by hand, and the release job would fail on publish.
- **Changelog rendering.** View `packages/aurora/CHANGELOG.md` rendered on GitHub. Under `## 2.2.1`, the second bullet shows `a21ba3e: - Exclude pending/rejected…` inline (I1), and the six following bullets render nested.
- **Post-merge publish.** After the merge, confirm that the release workflow publishes `@cobaltcore-dev/aurora@2.2.1` to npm, and that it does not try to publish the private `@cobaltcore-dev/dashboard`.

</details>

---

_Analyzed 2026-10-17 · commit `aa157d0` · read-only; CI from PR API; release PR light review (no review agents, no security-reviewer — no source changes) · skill: review-and-comment-pr_
