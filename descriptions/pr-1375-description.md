# Summary

Aligns the Security Group detail page with the Juno design system:
- heading structure;
- description list layout;
- button variants;
- tabs.

The Juno tabs are made fully controlled. The page now falls back to Rules when the RBAC Policies tab disappears while it is open.

**Why the description list stretched and spread its rows.**
- Since #1111 (`cf2e0ad0`), `TwoColumnDescriptionList` put `grid grid-cols-2` on a Juno `Stack`.
- A `Stack` is already a flex container, so the element carried both `display: flex` and `display: grid`. Which one won depended on stylesheet order.
- With the flex default `alignment` (stretch), the shorter column was pulled to the height of the taller one, and its rows spread out to fill it.
- The fix lets the `Stack` flexbox lay out the columns:
  - `alignment="start"`;
  - `flex-1 min-w-0` on both lists, so they stay equal width and long values still truncate.

**Why the Juno tabs need `activeItem`.**
- In Juno 9.4.0, `Navigation` keeps its own active item in state. It sets it on the first click, keyed by `value || children || label`.
- From then on, `NavigationItem` ignores its `active` prop.
- With only `active` and `onClick`, any change of `activeTab` that is not a click would leave the highlight on the old tab, for example the fallback below. The key would also be the translated label.
- `SecurityGroupTabs` therefore follows the controlled pattern already used by `ListToolbar` and the image list:
  - stable `value`s;
  - `activeItem` and `onActiveItemChange` on `TabNavigation`.

**Why the RBAC Policies content could stay on screen without its tab.**
- `SecurityGroupDetailsView.tsx` keeps `activeTab` in local state and never resets it.
- If `showRBACTab` turned false while RBAC was open (ownership or `canViewRBAC` changing), the tab disappeared but the panel kept rendering.

# Changes Made

## Client

- **`components/TwoColumnDescriptionList.tsx`.**
  - `Stack` with `alignment="start"` instead of `grid grid-cols-2`.
  - `min-w-0 flex-1` on both `DescriptionList`s.
  - The component is shared, so the Floating IP and Image detail pages get the same layout fix.
- **`SecurityGroupBasicInfo.tsx`.**
  - An `h2` "General Information" above the list; the page title stays `h1`.
  - The heading and the list are wrapped in a vertical `Stack gap="2"`, as on the Flavor detail page.
  - The left column is now ordered Name, Description, ID, Tags.
  - A bare `h2` is used rather than `ContentHeading`, because `ContentHeading` renders an `h1`.
- **`SecurityGroupRulesTable.tsx`, `SecurityGroupRBACPolicies.tsx`.**
  - "Add Rule" and "Share Security Group" use the default button variant.
  - "Edit Details" in the page header stays the only primary button on the page.
- **`SecurityGroupTabs.tsx`.**
  - The custom `Stack` of buttons is replaced with Juno `TabNavigation` / `TabNavigationItem`.
  - Each item has a stable `value` (`rules`, `rbac`).
  - `TabNavigation` gets `activeItem` and `onActiveItemChange`.
  - `active` is kept for the first render, before `activeItem` is applied.
- **`SecurityGroupDetailsView.tsx`.**
  - `currentTab` falls back to `rules` when the RBAC tab is not shown. Tabs and panels render from it.
  - `activeTab` itself is kept, so the RBAC tab reopens if it comes back.

# Related Issues

Fixes #

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Network → Security Groups → open a group owned by the current project:
   - **Heading and fields:** "General Information" is shown as a section heading under the page title. The left column lists Name, Description, ID and Tags.
   - **Layout:** the two columns are equal width. The shorter column keeps its rows together at the top instead of stretching to the height of the other one. Long values (ID, Owning Project ID) truncate.
   - **Buttons:** "Add Rule" (Rules tab) and "Share Security Group" (RBAC Policies tab) are default buttons. "Edit Details" in the header is still primary.
   - **Tabs:** switching between Rules and RBAC Policies highlights the selected tab and shows its content.
4. Open a group shared to the current project from another project: only the Rules tab is shown.
5. Open the Floating IP and Image detail pages and check that their description lists still lay out correctly.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
