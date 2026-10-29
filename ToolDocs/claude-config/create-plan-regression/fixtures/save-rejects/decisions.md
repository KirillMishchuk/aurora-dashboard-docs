## Decisions needed

Context from the analysis, so the options make sense:
- **The issue's screenshot is out of date.** It shows the hand-rolled `<button class="px-6 py-3 ... border-b-2">` tabs from before #1375. PR #1375 (merged 08.10.2026) already moved `SecurityGroupTabs.tsx` to Juno `TabNavigation`/`TabNavigationItem`. So the remaining work is renaming the deprecated `TabNavigation` to `TabBar`/`TabBarItem`. File: `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupTabs.tsx`.
- **No Juno version bump is needed.** The installed `@cloudoperators/juno-ui-components` 9.7.1 exports `TabBar` and `TabBarItem` (`build/index.d.ts:86,88`). In 9.7.1, `TabNavigation` and `TabNavigationItem` are thin wrappers, built with `withDeprecationWarning`, around `TabBar` and `TabBarItem`. The props are the same. The DOM is the same `role="navigation"` plus `<button aria-current>`, and the `activeItem` sync goes through the same `Navigation` component. The only difference is the default appearance: the wrapper defaults to `"main"`, `TabBar` defaults to `"tabs"`. Both render with the same item styles and no CSS targets those class names, so the change looks the same.
- **The Juno skills don't cover tabs.** The skills shipped in `node_modules/@cloudoperators/juno-ui-components/skills/` are only `datagrid*`. They have no `TabBar` guidance beyond one example snippet.
- **The tab state is local, not in the URL.** It lives in `useState<TabType>("rules")` in `SecurityGroupDetailsView.tsx`, and nothing in the URL needs preserving.

### D1. `.github/copilot-instructions.md` still names `TabNavigation` as the required tab component (line 130). Update it in this change?
- **A:** Change that row to `TabBar`, `TabBarItem` in this change. — Copilot's rules then match the issue's direction, and Copilot won't flag the new `TabBar` usage as a deviation. Until the five other `TabNavigation` users are migrated, the rule contradicts existing code (only new or changed code gets reviewed against it). The PR also touches a team-wide review file.
- **B:** Leave the file alone and propose a follow-up to update it together with the other scopes. — The PR stays limited to Security Groups. Copilot may comment that `TabBar` differs from the listed `TabNavigation`, and the reviewer would answer that the issue asks for it.
- **Recommendation:** A. The issue itself says `TabNavigation` is deprecated and `TabBar` replaces it, so the rule is already stale. Changing one table row keeps Copilot from pushing new code, including the pending migrations of the other scopes, back to the deprecated component.

### D2. Should the active tab (Rules / RBAC Policies) also move into the URL?
`copilot-instructions.md:345-353` says persistent UI state must live in URL search params (`tab`). Today it lives in `useState` in `SecurityGroupDetailsView.tsx`, which this change doesn't touch.
- **A:** Keep it in local state: only swap the component, as #1387 asks. — This is a small, low-risk diff. Refresh and deep links still always open "Rules", as they do today.
- **B:** Sync it to a `tab` search param in this change: add `validateSearch` to the detail route `$securityGroupId/index.tsx` and drive `activeTab` and `onTabChange` from `Route.useSearch()`/`navigate`. Keep the existing fallback to Rules when the RBAC tab is hidden. — This follows the Copilot rule and the `BucketDetailTabs` `view` precedent. It is out of the issue's scope, adds route-level changes and tests, and has to be combined carefully with the rules toolbar's existing URL params (search, sort, filter in `urlHelpers.ts`).
- **Recommendation:** A, with B proposed as a follow-up. The issue is a pure component swap. The sibling detail page `RouterDetailsView.tsx` also keeps its tab in `useState`, and Copilot only reviews changed lines, and the `useState` line in `SecurityGroupDetailsView.tsx` doesn't change.

Small choices I'll make in the plan unless you object:
- Use `TabBar`'s default `appearance` (`"tabs"`), which looks the same as today's look. I won't use `"content"`, the variant with a shared bottom border.
- Add `ariaLabel={t\`Security group sections\`}` to the `TabBar`. Juno recommends it when there is more than one `role="navigation"` on a page, and the sidebar nav is one. This adds one Lingui string, so `check-i18n` has to be run and the locale catalogs regenerated. The German catalog already has 696 untranslated entries, so an untranslated new one is normal.
- Keep the component's public API (`activeTab`, `onTabChange`, `showRBACTab`, `TabType`) and the existing tests, which already assert `role="button"` and `aria-current="true"`.
- Add a patch changeset for `@cobaltcore-dev/aurora`.
- List the other five `TabNavigation` users as one proposed follow-up: `client/components/ListToolbar/index.tsx`, `network/routers/-components/RouterDetailsView.tsx`, `storage/-components/Ceph/Buckets/BucketDetailTabs.tsx`, `storage/-components/Ceph/Objects/ObjectBrowserView.tsx` and `compute/images/-components/List.tsx`.

Relevant absolute paths:
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupTabs.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupTabs.test.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/SecurityGroupDetailsView.tsx` (and `.test.tsx`)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/index.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.github/copilot-instructions.md` (lines 130 and 345-353)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/node_modules/@cloudoperators/juno-ui-components/build/components/TabBar/TabBar.component.d.ts`, `.../TabBarItem/TabBarItem.component.d.ts`