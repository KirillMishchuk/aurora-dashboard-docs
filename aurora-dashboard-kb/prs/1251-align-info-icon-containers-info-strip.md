---
type: pr-report
date: 2026-09-02
status: merged
pr: [1251]
author: mark-karnaukh-extern-sap
branch: mark-fix-align-info-icon
---
# PR #1251: fix(aurora): align the info icon in the containers info strip (#1229)

**Author:** mark-karnaukh-extern-sap · **Status:** created 2026-09-01 → merged 2026-09-02
**Branches:** `mark-fix-align-info-icon` → `main` · **Files:** 2 (+7/-1)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1251

## What was done

Closes #1229: in the info strip above the Swift containers table (`N containers, Remaining Quota: …`), the hint icon (ⓘ) visually sat off-center relative to the adjacent text. The cause is the wrapping `TooltipTrigger`: by default (`asChild` not passed) it renders a native `<button>` around the passed children rather than handing styling to the icon itself; the button's browser-default paddings/border-box inflate the trigger's resulting height to roughly ~25px, while the icon itself (`Icon size="20px"`) is 20px. Inside a `flex items-center` row (`data-testid="containers-info-block"`), the taller trigger box is centered differently from single-line text, hence the visible shift.

The fix limits the trigger's height with the `max-h-5` class (Tailwind, `max-height: 1.25rem` = 20px), bringing the button box's height down to the height of the icon itself. The change is a one-liner, plus a changeset (`patch`) — no logic, props or component structure was touched.

## How it is implemented

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/ContainerLimitsTooltip.tsx:64-70
return (
  <Tooltip triggerEvent="hover" placement="bottom-end" open={open}>
    <TooltipTrigger className="max-h-5">
      <span>
        <Icon icon="info" size="20px" className="text-theme-light hover:text-theme-default cursor-pointer" />
      </span>
    </TooltipTrigger>
```

Checked against the source of `@cloudoperators/juno-ui-components`, pinned version `9.4.0` (`packages/aurora/package.json:86`, tag `@cloudoperators/juno-ui-components@9.4.0` in `juno/`) — with `asChild=false` (the path used here), `TooltipTrigger`'s `className` is passed directly into the native `<button>`'s attribute and is not combined with anything:

```tsx
// juno: packages/ui-components/src/components/TooltipTrigger/TooltipTrigger.component.tsx
return (
  <button
    ref={ref}
    data-state={state.open ? "open" : "closed"}
    {...state.getReferenceProps(props)}
    className={`${className} ${state.disabled && " jn:cursor-default"}`}
  >
    {children}
  </button>
)
```

I.e. there is no built-in height clamp in `TooltipTrigger` itself — the button's height is determined entirely by the `<button>` UA styles (paddings/border), and that is exactly what the fix compensates for from the outside via `className`.

Historical context (`git log` on the file, `origin/main`): using a plain `<button>` trigger instead of the former `asChild` is not an accident of this PR but a deliberate decision from #1124 (`13e2ae1d`, «fix(portal): swift container limits tooltip not showing on hover»): there, `Icon` under `asChild` did not forward the ref correctly, which kept the tooltip from opening on hover, and the fix deliberately switched to the default `<button>` trigger with the icon wrapped in a `<span>`. The extra button height that #1251 now removes was a side effect of that necessary fix — this change does not conflict with #1124; it eliminates its visual side effect without reverting the hover fix itself.

## What it affects

`git grep -n 'ContainerLimitsTooltip' origin/main -- '*.ts' '*.tsx'` — the only render site in the whole monorepo:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/index.tsx:401
<ContainerLimitsTooltip serviceInfo={serviceInfo} accountInfo={accountInfo} />
```

inside that very `data-testid="containers-info-block"` (`className="text-theme-light ml-auto flex items-center gap-1"`) — exactly the context described in the PR. The other matches are `ContainerLimitsTooltip.test.tsx` and a mock in `Containers/index.test.tsx`, both tests rather than consumers.

The change is purely presentational: one Tailwind utility on `TooltipTrigger`'s `className` prop, which (see above) affects nothing other than the button's resulting `class` attribute — the `asChild` path is not used here either before or after the PR, so the `cloneElement`/ref-merging branch in `TooltipTrigger` is not in play. The component's public contract (`ContainerLimitsTooltipProps`, children, tooltip structure) did not change. The only consumer is tested by the same file (`ContainerLimitsTooltip.test.tsx`), which the PR does not touch and which does not check height/classes — there is no risk of test regression; the blast radius is limited to the visual centering of one icon in one row of one view.

## Review

The diff was checked along five lines: compliance with [`CLAUDE.md`](../../CLAUDE.md) (the root one, taken from `DOCS/ToolDocs/claude-config/aurora-dashboard-config/CLAUDE.md`), a bug scan of the diff itself, historical context (`git log`/`git blame` on the file, see above — #1124), prior PR feedback (`git log --oneline` on the file — only 3 commits: #1124, #964 juno upgrade, #850 package move; nothing resembling an unresolved review thread), comment compliance (there are no comments in the file itself governing the trigger's height/styles — nothing to check against).

Compliance: the PR title `fix(aurora): align the info icon in the containers info strip (#1229)` — the `fix` type and the `aurora` scope are both in the `commitlint.config.mjs` lists (`types`/`scopes`), and the `<type>(<scope>): <subject>` format is followed. The changeset (`.changeset/heavy-dingos-lead.md`, `"@cobaltcore-dev/aurora": patch`) matches the convention of the repository's other changesets in form and level (`patch` for a targeted visual fix).

**No problems with confidence ≥80 were found.**

The only hypothesis considered that did not pass the threshold: that `max-h-5` might clip the icon if the actual content height (icon + button paddings) exceeds 20px. On checking — Tailwind `max-h-*` does not set `overflow: hidden` by itself (unlike `h-*` followed by `overflow-hidden`), and no `overflow` is set on `TooltipTrigger`/`button` anywhere in the diff or in the juno component, so overflow defaults to `visible` — the content won't be clipped even if the button paddings formally don't fit into 20px. Moreover, the trigger's only content is the 20px icon itself in a `<span>` without its own paddings, so the natural content height is exactly 20px anyway. Score: 15/100 (hypothetically possible in other browser engines with a different button UA style, but confirmed neither by the code nor by the author's checklist «Info icon is vertically aligned… Tooltip still opens on hover and is positioned correctly»).

---
Analyzed: 2026-09-02 · commit `7c1b89bc` (head, PR open/unmerged)
