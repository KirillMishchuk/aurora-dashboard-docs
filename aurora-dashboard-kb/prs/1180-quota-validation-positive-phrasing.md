---
type: pr-report
date: 2026-08-18
status: merged
pr: [1180]
author: mark-karnaukh-extern-sap
branch: mark-use-positive-quota-validation-message
---
# PR #1180: fix(portal): use positive phrasing for quota validation message

**Author:** mark-karnaukh-extern-sap · **Status:** merged 2026-08-21 (commit `a7b73a1e`; created 2026-08-18)
**Branches:** `mark-use-positive-quota-validation-message` → `main` · **Files:** 7 (+40/-16)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1180

## What was done

Fixes the validation error message for Swift container quotas (issue #1164, "Bug: use positive instruction, not double-negative"): instead of the double negative "Must be a non-negative integer" — a direct instruction "Must be a whole number, 0 or greater". Both quota fields are affected — `quota-bytes` (Total size quota) and `quota-count` (Object count quota) — in the `EditContainerMetadataModal` modal (Storage → Swift → Containers).

The PR consists of 4 commits: the wording change itself (`cdd7d55`), the translation update (`ae0dc58`), **a separate fix commit `f7f577c` "reject non-integer quota values"** that adds a `Number.isInteger` check — i.e. before this commit the validation let fractional values like `1.5` through, and this was fixed within the same PR — and finally the changeset (`2aeef4c`, the current head).

## How it is implemented

`validateQuotas` (`EditContainerMetadataModal.tsx:209-230`) checks both fields with three conditions instead of two:

```ts
// EditContainerMetadataModal.tsx:211-219
if (
  quotaBytes !== "" &&
  (isNaN(Number(quotaBytes)) || !Number.isInteger(Number(quotaBytes)) || Number(quotaBytes) < 0)
) {
  setQuotaBytesError(t`Must be a whole number, 0 or greater`)
  valid = false
} else {
  setQuotaBytesError(null)
}
```

The symmetric block for `quotaCount` is `EditContainerMetadataModal.tsx:220-228`, with the same three checks and the same error text. Both fields are plain `TextInput`s (not `type="number"`, `EditContainerMetadataModal.tsx:498-510`), and the state is strings (`useState("")`, lines 116/118), so all protection against non-integer/negative values rests on this manual check. On save (`EditContainerMetadataModal.tsx:328` — `if (!validateQuotas()) return`) the form is blocked on error; on success the value goes into the mutation as `Number(quotaBytes)` (`EditContainerMetadataModal.tsx:377`) — already safe, since `Number.isInteger` passed at the validation stage.

The tests (`EditContainerMetadataModal.test.tsx`) are updated to the new error text everywhere it was checked (previously "Must be a non-negative integer"), and a new case "shows validation error for decimal quota-bytes" is added (input `"1.5"` for Total size quota) — but no symmetric test for a fractional value of `quotaCount` is added, even though the code handles both fields identically.

Translations: `packages/aurora/src/locales/{en,de}/messages.po` — the old string `msgid "Must be a non-negative integer"` is removed, a new one `msgid "Must be a whole number, 0 or greater"` is added (German `"Muss eine ganze Zahl sein, 0 oder größer"`); the compiled `messages.ts` are regenerated along with it. Changeset `.changeset/witty-numbers-poke.md` — `patch` for `@cobaltcore-dev/aurora`, correct (a text edit + extended validation, with no change to the public contract).

## What it affects

`EditContainerMetadataModal` is not exported from the package — the only consumer is found in the same folder, `ContainerTableView.tsx` (`import { EditContainerMetadataModal } from "./EditContainerMetadataModal"`). The change is entirely internal and does not ripple outward (beyond the Swift Containers UI).

A search across the rest of the monorepo for similar quantity-validation wording (`non-negative`, `isInteger`) found only an unrelated neighbor — `EditImageDetailsModal.tsx` (Compute/Images, fields `min_disk`/`min_ram`) uses its own text "Minimum disk/RAM must be 0 or greater", already positive and not touched by this PR — not the same text that was changed here, so this is not a missed duplicate but an originally different wording; I mention it only to explicitly rule it out as a false finding.

**Important for the reader of this report:** the PR description ("Notes" section) states that "the validator does not check for integers" and characterizes this as an unresolved follow-up for a future UX review. This is outdated relative to the current head commit — commit `f7f577c`, already part of this PR, added exactly this check (`!Number.isInteger(...)`) before the changeset was created. At the time of analysis (head `2aeef4c`) integer validation is implemented and covered by a test.

## Review

No issues with confidence ≥80 were found. The logic is symmetric for both fields, the conversion into the payload (`Number(quotaBytes)`) is safe thanks to the preceding `Number.isInteger` check, the commit messages and scope (`portal`) conform to `commitlint.config.mjs`, and the changeset type is correct (`patch`). Below the threshold: the missing test for a fractional value of `quotaCount` (the code is identical to `quotaBytes`, the test asymmetry does not affect behavior) — a nitpick, not reported as a finding.

---
Analyzed: 2026-08-18 · commit `2aeef4c`
