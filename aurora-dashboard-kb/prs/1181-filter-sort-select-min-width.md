---
type: pr-report
date: 2026-08-18
status: merged
pr: [1181]
author: mark-karnaukh-extern-sap
branch: mark-fix-dropdown-select-min-width
---
# PR #1181: fix(portal): add min-width to filter/sort selects app-wide

**Author:** mark-karnaukh-extern-sap · **Status:** merged 2026-08-18 (commit `2309942`; created 2026-08-18)
**Branches:** `mark-fix-dropdown-select-min-width` → `main` · **Files:** 12 (+35/-6)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1181

## What was done

Closes issue #1135: the filter/sort dropdowns (`Select`/`ComboBox` from `ListToolbar`) changed width depending on the currently selected value — short text shrank the menu, long text stretched it, which made the whole toolbar "jump" when the value changed. The PR gives these selects a minimum width without touching the option/selection logic (the PR description states this explicitly — "Behaviour only", confirmed by the diff: changes only to `className`).

4 commits: the first (`4abd695`) naively set `min-w-40` everywhere, the second (`6c1e79f`) switched `FiltersInput` to a `cn()` merge instead of manual class concatenation, the third (`ef6a382`) narrowed the scope of the min-width in `FiltersInput` to the `sm:` breakpoint — following a direct CodeRabbit comment that at the `sm` breakpoint the filter could still shrink, because a class with a non-matching variant did not override the conflicting `sm:min-w-0` — and the fourth (`c089ec5`, current head) added a changeset.

## How it is implemented

`FiltersInput` (`FiltersInput.tsx`) got two new optional props and switched to `cn()` (clsx + tailwind-merge) for joining classes:

```tsx
// FiltersInput.tsx:12-13, 30-35
selectClassName?: string
comboboxClassName?: string
...
export const FiltersInput = ({
  filters,
  onChange,
  selectClassName = "",
  comboboxClassName = "",
}: FiltersInputProps) => {
```

```tsx
// FiltersInput.tsx:62, 73
className: cn("w-full sm:min-w-0 sm:flex-1", selectClassName),   // Select
className: cn("w-full sm:min-w-0 sm:flex-1", comboboxClassName), // ComboBox
```

Why the `sm:` prefix on the passed class specifically matters: `cn` = `twMerge(clsx(...))` (`packages/aurora/src/client/utils/cn.ts`), and `twMerge` resolves conflicts by the utility's **variant**, not by order in the class string. The unprefixed `min-w-40` and `sm:min-w-0` are, for `twMerge`, different variants of the same group; it sees no conflict and keeps both; and since in the compiled Tailwind CSS the rules for the `sm:` variant physically come after the unprefixed ones in the stylesheet, `sm:min-w-0` wins on screens ≥`sm` regardless of the order of the classes in the attribute. That is why all 4 places where `FiltersInput` is actually used got `sm:min-w-40` specifically (not `min-w-40`) — this is exactly the third commit's fix, which closes the CodeRabbit finding.

`SortInput` (`SortInput.tsx:31` — `className: selectClassName`, no base class and no `cn()`) has no such conflict — a plain `min-w-40` works as intended there, so all 10 places where `SortInput` is rendered got the unprefixed `min-w-40` (7 — newly setting the prop, 3 — extending the already existing `selectClassName` from `w-40` to `min-w-40`, so that the sort select does not shrink below 10rem but can grow for a longer value).

## What it affects

All real consumers of `FiltersInput` (4: `Images/List.tsx`, `FloatingIpsList.tsx`, `SecurityGroupRulesTable.tsx`, `SecurityGroupsList.tsx`) and `SortInput` (10, see above) in the monorepo were checked — all are updated consistently, no missed places found. The comment in `Swift/Containers/index.tsx:316-317` about "add FiltersInput alongside the search" is a TODO for the future (there are no filters yet), not a missed call.

There is one consumer of both components that the PR does not touch: the composite `ListToolbar` (`packages/aurora/src/client/components/ListToolbar/index.tsx:180,185`) renders `<FiltersInput {...filtersProps} />` and `<SortInput {...sortProps} />`, but passes `selectClassName`/`comboboxClassName` through neither in its own props nor in `filtersProps`/`sortProps`. In practice this does not create a bug right now — `ListToolbar` is not imported by any real route/component (only by its own `index.test.tsx`); it is an unused composite, apparently groundwork for a future consolidation of the duplicated toolbar pattern across 6+ lists. Worth keeping in mind: if/when `ListToolbar` gets wired in, it will need these props too.

The changeset `.changeset/nice-beans-poke.md` (`patch` for `@cobaltcore-dev/aurora`) was added in the fourth commit (`c089ec5`) — it matches the scale of the change (a styling fix, no contract change).

## Review

No issues with confidence ≥80 found. The `cn()`/`sm:` scoping mechanics after the third commit are correct (verified against the `cn.ts` source and the actual class conflict, not against the PR description), coverage of all `FiltersInput`/`SortInput` call sites is complete, the changeset is in place. The absence of new tests for the `selectClassName`/`comboboxClassName` props themselves is below the threshold (CLAUDE.md does not require coverage for styling props) and is not reported as a finding.

> At the time of the first pass (head `ef6a382`), the changeset was missing — this was noted as a finding [85]. Commit `c089ec5` added it before the review was completed; the final version of the report reflects the current head and does not contain that finding.

---
Analyzed: 2026-08-18 · commit `c089ec5`
