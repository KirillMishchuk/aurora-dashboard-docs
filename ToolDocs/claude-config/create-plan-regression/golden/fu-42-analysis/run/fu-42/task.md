# Task: follow-up item 42 from DOCS/FOLLOW-UPS.md

Treat it as the task's spec and refer to it by its number.

### 42. `TabNavigation` tabs: `tabStyle="content"` and a controlled `activeItem` everywhere

**Where:** all five `TabNavigation` instances in `packages/aurora/src/client`: `components/ListToolbar/index.tsx:163`,
`compute/images/-components/List.tsx:247`, `storage/-components/Ceph/Buckets/BucketDetailTabs.tsx:21`,
`storage/-components/Ceph/Objects/ObjectBrowserView.tsx:655`,
`network/securitygroups/$securityGroupId/-components/-details/SecurityGroupTabs.tsx`.

**What, in two parts:**

1. **`tabStyle`.** It is not set anywhere, so `main` is used by default everywhere. According to the Juno 9.4.0 docs
   (`TabNavigation.component.tsx:77`), `main` is for the first child of AppShell; tabs inside a
   page need `content` (inactive tabs get a dark bottom border). All five sit
   inside a page.
2. **Semi-controlled tabs.** `BucketDetailTabs` and `ObjectBrowserView` pass only `active` +
   `onClick`. In Juno 9.4.0, after the first click `Navigation` keeps the active item in its own state, and
   `NavigationItem` then ignores `active`: if the tab is switched by something other than a click, the highlight stays
   on the old one. The item key in this case is the translated `label`. `ListToolbar`, `images/List.tsx` and
   `SecurityGroupTabs` are already controlled.

**How:**
1. `tabStyle="content"` in all five places at once, not one page at a time, and check the look in the browser.
2. In `BucketDetailTabs` and `ObjectBrowserView`, do it as in `SecurityGroupTabs.tsx`: a stable
   `value` on the items, `activeItem` + `onActiveItemChange` on `TabNavigation`, keep `active` for
   the first render. Test: click, then change the active tab from the parent via `rerender`, check
   `aria-selected`.

**Why not done right away:** it touches other people's pages (Ceph, Images, lists). Changing `tabStyle`
only for Security Groups would introduce a new inconsistency.

**Source:** /triple-review of the PR for the SG details page (branch `kiryl-security-groups-detail-page`),
2026-10-07.

**Status:** open.
