---
type: pr-report
date: 2026-09-04
status: merged
pr: [1270]
author: mark-karnaukh-extern-sap
branch: mark-fix-parse-timestamps-as-utc
---
# PR #1270: fix(aurora): time doesn't match current timezone (#1236)

**Author:** mark-karnaukh-extern-sap · **Status:** 2026-09-03 → merged 2026-09-04
**Branches:** `mark-fix-parse-timestamps-as-utc` → `main` · **Files:** 8 (+159/-26)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1270

## What was done

In its JSON listings of containers and objects, Swift returns `last_modified` as ISO 8601 **without a zone designator** — `"2024-03-01T08:00:00.000000"` (Swift bug #1169287). Per ISO 8601, a date-time without a zone is interpreted as **local** time, so `new Date("...T08:00:00").toLocaleString()` performed no UTC→local conversion and displayed a time shifted by the viewer's zone offset (issue #1236, reporter guoda-puidokaite).

The PR introduces a shared helper `@/client/utils/formatSwiftDate.ts` with two functions — `parseSwiftDate` (normalizes a zoneless timestamp to UTC by appending `Z`) and `formatSwiftDate` (a wrapper around `toLocaleString` that returns `null` on invalid input so that the caller chooses its own fallback) — and moves all Swift code that touches `last_modified` onto it: two tables (containers, objects), two sort comparators and the object metadata modal. A zone-independent unit test and a changeset (`patch` for `@cobaltcore-dev/aurora`) were added. Ceph is not affected — it returns timestamps with `Z`, and the helper passes such values through unchanged.

**Important:** the PR description lists only the helper, the two tables and the test under "Changes". The actual diff is broader — it also includes both sort comparators (`Containers/index.tsx`, `Objects/index.tsx`) and `EditObjectMetadataModal.tsx`. These three places were added later, in response to a Copilot comment, and it is precisely in the modal that the regression from the "Review" section lives. Read the diff, not the description.

## How it is implemented

The core is a "does the string have a zone" heuristic in `formatSwiftDate.ts`:

```ts
const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/

export const parseSwiftDate = (value: string | null | undefined): Date | null => {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed) return null

  // Only a full date-time (has a "T") that lacks a zone needs normalizing to
  // UTC. A date-only string ("2024-03-01") is already parsed as UTC by the
  // engine, and appending "Z" to it would make it invalid.
  const needsUtc = trimmed.includes("T") && !HAS_ZONE.test(trimmed)
  const normalized = needsUtc ? `${trimmed}Z` : trimmed

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}
```
— `packages/aurora/src/client/utils/formatSwiftDate.ts:21-40`

`formatSwiftDate` (same file, `:50-57`) is a thin wrapper: `parseSwiftDate` plus `date.toLocaleString(locales, options)`, returning `null` instead of a placeholder string.

**Tables.** Both tables had their own local `formatDate`; both were removed and replaced with a call to the helper, keeping each place's previous fallback:

```tsx
<DataGridCell>{formatSwiftDate(container.last_modified) ?? t`N/A`}</DataGridCell>
```
— `.../Swift/Containers/ContainerTableView.tsx:232` (similarly `.../Swift/Objects/ObjectsTableView.tsx:409-410`, where the fallback is a literal `"—"`)

**Sorting.** Both comparators previously computed `new Date(a.last_modified).getTime() - new Date(b.last_modified).getTime()`, i.e. they compared incorrectly parsed instances (around DST transitions this produced a genuinely wrong order). The new version in containers also fixes transitivity for missing values:

```ts
case "last_modified": {
  // Both missing → equal (keeps the comparator transitive); exactly one
  // missing → push it to the end.
  if (!a.last_modified && !b.last_modified) return 0
  if (!a.last_modified || !b.last_modified) {
    return a.last_modified ? -1 : 1
  }
  // #1236: Swift listing timestamps are UTC without a "Z" — parse them as
  // UTC so the ordering is correct (matters near DST boundaries). If a
  // (non-empty) value can't be parsed, treat the pair as equal so the
  // order is left untouched (matches the old NaN behaviour).
  const at = parseSwiftDate(a.last_modified)?.getTime()
  const bt = parseSwiftDate(b.last_modified)?.getTime()
  comparison = at == null || bt == null ? 0 : at - bt
  break
}
```
— `.../Swift/Containers/index.tsx:197-212` (the same in `.../Swift/Objects/index.tsx:354-366`)

The remark in the comment about "matches the old NaN behaviour" is substantively correct: the old code returned `NaN` from the comparator, and the `Array.prototype.sort` spec coerces a `NaN` result to `+0` — i.e. the same "treat the pair as equal". Verified by running on mixed arrays: the sort behavior is identical.

**Metadata modal.** `EditObjectMetadataModal` is the only place that deliberately shows time in UTC (its field labels are `Last modified (UTC)`, `Expires at (UTC)`), so `timeZone: "UTC"` is kept, and the function body is rewritten onto the helper:

```tsx
const formatDate = (iso: string): string =>
  // #1236: Swift timestamps are UTC without a "Z"; parse them as UTC (via
  // formatSwiftDate) so the value is correct. This view intentionally displays
  // in UTC (timeZone: "UTC"), unlike the list tables which show local time.
  formatSwiftDate(iso, undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) ?? "—"
```
— `.../Swift/Objects/EditObjectMetadataModal.tsx:77-88`

The history confirms that this UTC is an old deliberate decision (introduced together with the modal itself in `919f89e9`, reconfirmed in `0c4b2010` when unifying the format with the editable field), whereas "local time" in the tables was never deliberately chosen: since their creation (`4e369750`, `93413009`) they had an argument-less `toLocaleString()`. So the current mix of "tables — local, modal — UTC" does not contradict the history.

**Test.** `formatSwiftDate.test.ts` (62 lines) is built to be zone-independent: it checks not the formatted string in the runner's zone but the instant itself (`toISOString()`), and for formatting — two explicit zones (`UTC` and `America/New_York`), which proves that the conversion happens. The `try/catch` removed from `ContainerTableView` had been dead code since the file's very first commit: `new Date()` does not throw, it returns `Invalid Date`.

## What it affects

**There are no missed places — this was verified, not assumed.** `git grep` for `last_modified` at `d6d81280` shows that no place remains in the Swift components where `last_modified` is parsed directly: the other `new Date(...)` calls in this directory work with unix seconds (`GenerateTempUrlModal.tsx:249`, `formatUnixToTimestamp`) or with a field-format string `"YYYY-MM-DD HH:mm:ss"`, to which `Z` is appended explicitly (`EditObjectMetadataModal.tsx:53`, `:244`) — that is a separate contract and does not need the helper.

**Ceph is deliberately untouched and does not need this.** `Ceph/Buckets/index.tsx:196` and `Ceph/Objects/ObjectBrowserView.tsx:364,401` still use raw `new Date(...)`, but Ceph returns timestamps with `Z`, so parsing there is correct. It was separately verified that `ObjectBrowserView` is Ceph-only (exported as `CephObjects`; for Swift, the shared route `storage/$provider/$storageType/$containerName/objects` renders a different component), even though its `SortKey` also accepts the Swift key `last_modified` for compatibility.

**The package's public API is not extended.** The helper lives in `client/utils/` and is not exported from `packages/aurora/src/client/index.ts` — there are no external consumers; all 5 imports are within the PR itself. For embeddable sub-apps (SCI) the surface has not changed; the change is internal.

**Existing tests give no signal.** `ContainerTableView.test.tsx:294` and `EditObjectMetadataModal.test.tsx:259` only check that a string/label is present, not a specific time value, and they use zoneless fixtures. No test in the affected components asserts either a specific formatted date or the sort order by `last_modified` — this is a pre-existing gap, but it is exactly what masks the regression below.

## Review

Five parallel agents (convention compliance, bug scan, history, past feedback, comment compliance) plus confidence scoring. One finding passed the ≥80 threshold. The repository at `d6d81280` has no tracked [`CLAUDE.md`](../../CLAUDE.md)/`AGENTS.md` (`.gitignore` excludes `CLAUDE*`), so the "against the guidelines" check relied on the actual conventions of the neighboring code.

### [100] Regression: `Last modified (UTC)` in the object metadata modal now always shows `—`

`needsUtc` determines "this is a date-time" by a substring search for the letter `T` anywhere in the string:

```ts
const needsUtc = trimmed.includes("T") && !HAS_ZONE.test(trimmed)
```
— `packages/aurora/src/client/utils/formatSwiftDate.ts:35`

There is no position check, so the condition also fires on the letter `T` inside the word **`GMT`**. And what reaches the modal is not a listing timestamp but the raw HTTP `Last-Modified` header in RFC 1123 format — it is put into the metadata unchanged on the server:

```ts
const lastModified = headers.get("last-modified")
if (lastModified) {
  metadata.lastModified = lastModified
}
```
— `packages/aurora/src/server/Storage/helpers/swiftHelpers.ts:250-252`

and it reaches `formatDate` with priority, ahead of the listing value:

```tsx
{metadataRaw?.lastModified
  ? formatDate(metadataRaw.lastModified)
  : object.last_modified
    ? formatDate(object.last_modified)
    : "—"}
```
— `.../Swift/Objects/EditObjectMetadataModal.tsx:436-439`

The chain on a real value (verified by running in node on the same V8):

| step | result |
| --- | --- |
| input | `"Wed, 01 Mar 2025 12:00:00 GMT"` |
| `trimmed.includes("T")` | `true` — from `GMT` |
| `HAS_ZONE.test` | `false` — `GMT` does not match `Z` / `±hh:mm` at the end |
| `normalized` | `"Wed, 01 Mar 2025 12:00:00 GMTZ"` |
| `new Date(...)` | `Invalid Date` → `parseSwiftDate` returns `null` |
| rendered | `"—"` |
| **old code** `new Date(iso)` | `2025-03-01T12:00:00.000Z` — parsed correctly |

So this is a **strict regression on the main path**: the HEAD request for object metadata normally succeeds, practically every object has a `Last-Modified` header, and the field that used to show the real time now shows a dash every time the modal is opened. The PR's test does not catch this because it mocks `lastModified` as an ISO string (`EditObjectMetadataModal.test.tsx:117,259`), not as a real HTTP-date.

Found independently by two agents (bug scan and comment compliance), confirmed by directly running the parsing and tracing the data source back to `swiftHelpers.ts`. The fix is to anchor the check to a position — e.g. testing for the ISO form (`/^\d{4}-\d{2}-\d{2}T/`) instead of `includes("T")`, or an explicit branch for HTTP-date.

### Below the threshold (as context, not as tasks)

- **[25]** The comment at `formatSwiftDate.ts:34` claims that appending `Z` to a date-only string "would make it invalid" — factually incorrect (`new Date("2024-03-01Z")` parses to the same instant). Harmless: the code appends `Z` only when a `T` is present, so date-only strings never reach this branch. Incorrect rationale, correct behavior.
- **[50]** `formatSwiftDate.test.ts` uses `test(...)`, whereas all five existing `client/utils/*.test.ts(x)` files use `it(...)` exclusively. Purely stylistic; neither the linter nor a guidelines file requires this.
- **[25]** Copilot's comment on `formatSwiftDate.ts:36` (that the comparators and `formatDate` are still on raw `new Date`) is already outdated at `d6d81280` — all three places have been moved to the helper; the thread just isn't marked resolved. The author fixed its other comments (comparator transitivity, `?? 0` as epoch 1970) and replied in the thread.

---
Analyzed: 2026-09-04 · commit `d6d81280`
