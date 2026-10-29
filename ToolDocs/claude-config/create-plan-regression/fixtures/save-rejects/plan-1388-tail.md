## Overview

Issue #1388 (epic #1327) asks for consistent empty-state messages on the Security Group detail page. Every title should be in title case. Each message should also pass an explicit, specific `body`, instead of falling back to the English-only default body of Juno `Status` ("There are no items to display."). This plan changes three empty states:
- the RBAC Policies tab when there are no policies (the issue's exact text)
- the RBAC Policies tab when a search matches nothing (D1)
- the Rules tab when there are no rules (D2)

It also updates the Lingui catalogs (en and de), the unit tests and a patch changeset.

## Decisions

- **D1.** The RBAC "search matches nothing" message is changed too (option B). It gets its own `<Status status="no-matches">` with title `No Matching RBAC Policies Found` and body `There are no RBAC Policy items matching your search. Try adjusting your search term.` The no-policies message uses exactly the issue's text: title `No RBAC Policies Found`, body `There are no RBAC Policy items to display for this Security Group.`
- **D2.** The Rules tab is aligned too (option B): title `No Rules Found`, body `There are no Rule items to display for this Security Group.`
- **Settled without asking (they follow repo conventions):**
  - Commit type/scope `fix(portal)`.
  - A `"@cobaltcore-dev/aurora": patch` changeset.
  - Re-run `check-i18n` and include all four regenerated locale files.
  - Fill in German `msgstr` for the new strings, because the replaced strings had German translations.

## Architecture Analysis

**Current state:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRBACPolicies.tsx:174-183`: a single `<Status status="empty">` whose `title` is ``searchTerm ? t`No policies match your search` : t`There are no RBAC policies for this security group` ``. There is no `body`. `filteredPolicies` (l.97-109) is filtered on the client from `searchTerm`.
- `.../-details/SecurityGroupRulesTable.tsx:242-247`: `<Status status="empty" title={t`There are no rules for this security group`} />`, no `body`. The parent `SecurityGroupDetailsView.tsx:78-83` passes `rules={filteredAndSortedRules}`, which is already filtered. So this message also appears when a search or filter hides every rule. That stays as it is (see Risks and Proposed follow-ups).
- Juno `Status` (pinned `@cloudoperators/juno-ui-components` 9.7.1, in `packages/aurora/package.json`): `title ?? default`, `body ?? default`. The defaults are `empty` → "No Items" / "There are no items to display." and `no-matches` → "" / "No items match the current filters. Adjust or clear filters." Passing an explicit `title` and `body` overrides both. The Juno prop docs ask for title case in titles.
- Existing pattern for a separate "no search results" state: `storage/-components/Ceph/Buckets/CorsRulesTable.tsx:127-129` and `LifecycleRulesTable.tsx:137`. They use `status="no-matches"` for search misses and `status="empty"` otherwise. Pages that already use the "No X Found" + specific-body copy: `FloatingIpListContainer.tsx:41-42`, `RouterListContainer.tsx:81`.
- Lingui: `packages/aurora/lingui.config.js` uses PO format with `origins: false`, locales `de` and `en`. The `check-i18n` script is `lingui extract --clean && lingui compile --typescript`. All four `src/locales/{en,de}/messages.{po,ts}` files are committed, and every recent feature PR includes their regenerated versions (e.g. ee58286d, af14a6a0). `extract --clean` removes the obsolete msgids, along with their German translations.
- Existing German entries for reference:
  - "There are no RBAC policies for this security group" → "Für diese Security Group sind keine RBAC-Richtlinien vorhanden"
  - "No policies match your search" → "Keine Richtlinien entsprechen Ihrer Suche"
  - "There are no rules for this security group" → "Es gibt keine Regeln für diese Sicherheitsgruppe"
  - "No Rules Found" already exists (used by `storage/.../DeleteCorsRuleModal.tsx:179`) with an empty German `msgstr`.
- Changesets: every recent product PR adds a `.changeset/*.md` with `"@cobaltcore-dev/aurora": patch`, e.g. `.changeset/security-groups-detail-page-improvements.md` in ee58286d.

**Proposed changes:**

- Change only the copy and the `status` value on the three `Status` elements. No logic, props or data flow change.
- Follow the CorsRulesTable pattern for the search/empty split.
- Regenerate the catalogs with the repo script and fill in German translations by hand.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Unit tests assert the old strings (`SecurityGroupRBACPolicies.test.tsx:239,392,692`, `SecurityGroupRulesTable.test.tsx:117,134`, `SecurityGroupDetailsView.test.tsx:504`) | Medium | Update every assertion in Step 3. Grep for the old strings afterwards to confirm none are left. |
| `"No Rules Found"` is the same msgid as in `DeleteCorsRuleModal.tsx:179`, so the two share one catalog entry | Low | This is intended. Filling its German `msgstr` also translates the CORS modal title, which is an improvement. Use a neutral translation ("Keine Regeln gefunden") that fits both. |
| `extract --clean` drops the old German translations. If the German `msgstr` is not filled before `compile`, the German UI falls back to English | Low | Step 2 fills the German entries and then compiles again. Verify that `de/messages.ts` contains the German text. |
| The Rules tab shows "No Rules Found / … for this Security Group." when rules exist but a search or filter hides all of them (`rules` arrives already filtered) | Low | The behavior already exists (the old copy had the same issue). Out of scope for D2; listed under Proposed follow-ups. |
| Merge conflict with open issue #1387 (Tabs → ui-components), which touches `SecurityGroupTabs.tsx` | Low | Different file. Catalog conflicts are fixed by re-running `check-i18n`. |
| `status="no-matches"` changes the `Status` default copy | Low | Both `title` and `body` are always passed explicitly, so the defaults are never shown. The root keeps `role="status"`, as `empty` does. |

## Prerequisites

- [ ] None. No mock extension or dependency change is needed. The local mock already has a security group with no rules or RBAC policies (`empty-unused`) and one with 2 RBAC policies (`k8s-nodes`).

## Implementation Steps

### Step 1: Update the empty-state copy in both components

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRBACPolicies.tsx`: the empty branch at l.174-183.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx`: l.245.

**What to do:**

1. In `SecurityGroupRBACPolicies.tsx`, replace the single `<Status status="empty" title={searchTerm ? … : …} />` with a ternary over two elements, still inside the same `DataGridRow`/`DataGridCell colSpan={RBAC_COLUMN_COUNT}`:
   ```tsx
   {searchTerm ? (
     <Status
       status="no-matches"
       title={t`No Matching RBAC Policies Found`}
       body={t`There are no RBAC Policy items matching your search. Try adjusting your search term.`}
     />
   ) : (
     <Status
       status="empty"
       title={t`No RBAC Policies Found`}
       body={t`There are no RBAC Policy items to display for this Security Group.`}
     />
   )}
   ```
   Keep the `isPending` and `isError` branches and the outer `filteredPolicies.length === 0` condition unchanged. Use the strings exactly as written; the issue text is missing its closing quote, but the sentence ends with a period.
2. In `SecurityGroupRulesTable.tsx` l.245, replace the element with:
   ```tsx
   <Status
     status="empty"
     title={t`No Rules Found`}
     body={t`There are no Rule items to display for this Security Group.`}
   />
   ```
   Don't add new search-aware branching here (out of scope, see follow-ups).
3. Keep using the `t` from `useLingui()` already in scope in both files. No import changes.

**Expected outcome:** the three states render the new title and body. Juno's default "There are no items to display." no longer appears on either tab.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` and `pnpm --filter @cobaltcore-dev/aurora lint` pass. `eslint-plugin-lingui` should not flag anything, since all strings go through `t`.

---

### Step 2: Regenerate the Lingui catalogs and add German translations `[CAREFUL]`

**Files to modify (generated, but committed):**

- `packages/aurora/src/locales/en/messages.po`, `packages/aurora/src/locales/en/messages.ts`
- `packages/aurora/src/locales/de/messages.po`, `packages/aurora/src/locales/de/messages.ts`

**What to do:**

1. Run `pnpm --filter @cobaltcore-dev/aurora check-i18n`. It extracts with `--clean` and compiles.
2. Confirm in the `.po` diff that these msgids are gone: "There are no RBAC policies for this security group", "No policies match your search", "There are no rules for this security group". Confirm these were added: "No RBAC Policies Found", "There are no RBAC Policy items to display for this Security Group.", "No Matching RBAC Policies Found", "There are no RBAC Policy items matching your search. Try adjusting your search term.", "There are no Rule items to display for this Security Group.". "No Rules Found" already exists. The English `msgstr` values are filled in automatically.
3. In `de/messages.po`, set these German `msgstr` values (edit only the `msgstr` lines and keep the PO format):
   - `No RBAC Policies Found` → `Keine RBAC-Richtlinien gefunden`
   - `There are no RBAC Policy items to display for this Security Group.` → `Für diese Security Group sind keine RBAC-Richtlinien zum Anzeigen vorhanden.`
   - `No Matching RBAC Policies Found` → `Keine passenden RBAC-Richtlinien gefunden`
   - `There are no RBAC Policy items matching your search. Try adjusting your search term.` → `Keine RBAC-Richtlinien entsprechen Ihrer Suche. Passen Sie Ihren Suchbegriff an.`
   - `No Rules Found` (currently empty) → `Keine Regeln gefunden`
   - `There are no Rule items to display for this Security Group.` → `Für diese Sicherheitsgruppe sind keine Regeln zum Anzeigen vorhanden.`

   The wording reuses each replaced string's existing German terms: "Security Group" for RBAC and "Sicherheitsgruppe" for rules.
4. Run `pnpm --filter @cobaltcore-dev/aurora check-i18n` again so `de/messages.ts` contains the translations. Extract keeps the filled `msgstr`.

**Expected outcome:** the catalog diff is limited to these entries plus the regenerated single-line `messages.ts` files. No unrelated msgids are added or removed.

**Verification:**
- `git diff --stat packages/aurora/src/locales` shows only the four files.
- `grep -c "Keine RBAC-Richtlinien gefunden" packages/aurora/src/locales/de/messages.ts` returns 1.
- A third `check-i18n` run leaves no further diff.
- If the `.po` diff contains unrelated churn, main's catalogs were out of date. Keep it, because CI regenerates the same result, but mention it to the user.

---

### Step 3: Update unit tests

**Files to modify:**

- `.../-details/SecurityGroupRBACPolicies.test.tsx`
- `.../-details/SecurityGroupRulesTable.test.tsx`
- `.../-components/SecurityGroupDetailsView.test.tsx`

**What to do:**

1. `SecurityGroupRBACPolicies.test.tsx`:
   - l.239 ("renders empty state when no policies") and l.692 ("handles undefined policies data gracefully"): replace the old assertion with assertions for `"No RBAC Policies Found"` and `"There are no RBAC Policy items to display for this Security Group."`.
   - In the l.239 test, also add `expect(screen.queryByText("There are no items to display.")).not.toBeInTheDocument()` to guard against a fallback to the Juno default.
   - l.392 (search with no match, inside `waitFor`): assert `"No Matching RBAC Policies Found"` and `"There are no RBAC Policy items matching your search. Try adjusting your search term."`. Also assert that `"No RBAC Policies Found"` is not shown.
2. `SecurityGroupRulesTable.test.tsx` l.117 and l.134: assert `"No Rules Found"` and `"There are no Rule items to display for this Security Group."`. Leave the l.134 test's name and setup alone (it passes `searchTerm` but `rules=[]`, and the expected copy is the same).
3. `SecurityGroupDetailsView.test.tsx` l.504: assert `"No Rules Found"`. Add the body assertion if the test intends to check the empty state.

**Expected outcome:** the tests describe the new copy.

**Verification:**
- `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/network/securitygroups'` passes.
- `grep -rn "There are no RBAC policies for this security group\|No policies match your search\|There are no rules for this security group" packages/aurora/src --exclude-dir=locales` returns nothing.

---

### Step 4: Add a changeset

**Files to create:**

- `.changeset/security-groups-empty-state-copy.md`

**What to do:** create the file with this content:

```md
---
"@cobaltcore-dev/aurora": patch
---

Use title-case titles and specific body text for the Security Group detail page empty states (RBAC Policies empty and no-search-results states, Rules empty state) instead of the generic default body.
```

**Expected outcome / Verification:** `pnpm changeset status` lists `@cobaltcore-dev/aurora` as a patch bump.

## Testing Plan

**Unit tests** (vitest, colocated):

- [ ] RBAC with `data: []` renders "No RBAC Policies Found" and the issue's body, and does not render "There are no items to display.".
- [ ] RBAC with `data: undefined` renders the same empty state.
- [ ] An RBAC search with no matches renders "No Matching RBAC Policies Found" and its body, and not the no-policies title.
- [ ] The Rules table with `rules=[]` renders "No Rules Found" and its body, with and without `searchTerm`.
- [ ] The `SecurityGroupDetailsView` empty-rules case renders "No Rules Found".
- [ ] Full suite: `pnpm --filter @cobaltcore-dev/aurora test`.

**Manual check on the local mock** (`../local-mock-backend/`, start with `./run-all.sh`, then `pnpm dev`):

1. Network → Security Groups → `empty-unused`. The Rules tab shows "No Rules Found" with "There are no Rule items to display for this Security Group.".
2. Open the RBAC Policies tab of `empty-unused`. It shows "No RBAC Policies Found" with "There are no RBAC Policy items to display for this Security Group.". If that group does not show the RBAC tab (permission-dependent), use any of the `app-svc-*` groups without RBAC.
3. Open `k8s-nodes` → RBAC Policies (2 policies) and search for `zzz-nonexistent`. After the debounce it shows "No Matching RBAC Policies Found" with the search body. Clear the search and the policies come back.
4. Switch the UI language to German, if the app's locale switch is available, and repeat steps 1-3. The German strings appear.

**Live-environment checks:** none. This is a copy-only change with no OpenStack behavior involved.

## Acceptance Criteria

- [ ] The RBAC empty state shows exactly `No RBAC Policies Found` / `There are no RBAC Policy items to display for this Security Group.`.
- [ ] The RBAC search miss shows `status="no-matches"` with `No Matching RBAC Policies Found` / `There are no RBAC Policy items matching your search. Try adjusting your search term.`.
- [ ] The Rules empty state shows `No Rules Found` / `There are no Rule items to display for this Security Group.`.
- [ ] Juno's default "There are no items to display." no longer appears on either tab.
- [ ] `en`/`de` `.po` and `.ts` catalogs are regenerated. The German `msgstr` values are filled for all new strings and for "No Rules Found".
- [ ] A `.changeset/*.md` with an `@cobaltcore-dev/aurora` patch bump exists.
- [ ] No regressions: the loading and error states and the policy and rule rows render as before.
- [ ] `pnpm --filter @cobaltcore-dev/aurora lint`, `typecheck`, `test` and `check-i18n` pass, and `pnpm format:check` passes.

## Open Questions

- The German wording above is a proposal. A native speaker on the team can adjust it in the `.po` without changing the plan.
- The scope for the eventual commit and PR title is `fix(portal)`. `fix(network)` is also allow-listed, and the implementer can pick whichever matches recent security-group PRs.

## Proposed follow-ups

### Rules tab has no separate "no search/filter results" state

- **Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx:242-247` (receives already-filtered `rules` from `SecurityGroupDetailsView.tsx:78-83`)
- **What:** when the group has rules but the search or filters hide all of them, the table still says "No Rules Found / There are no Rule items to display for this Security Group.". That is misleading, and `.github/copilot-instructions.md` B.6 says these two cases should be told apart.
- **How to fix:** pass a total-rule count, or an `isFiltered` flag, from `SecurityGroupDetailsView`. Render `<Status status="no-matches">` with a title-case title and a body that suggests adjusting the search or filters when the table is filtered, mirroring the RBAC tab after this change.
- **Why not in this plan:** it needs new data flow between the parent and the table plus new copy, beyond the copy-only change D2 approved.

### Sentence-case empty-state titles elsewhere in the portal

- **Where:** e.g. `storage/-components/Ceph/Objects/ObjectsTableView.tsx:389` (`No objects found.` / `There are no items to display.`), `storage/-components/Ceph/Objects/ObjectVersionHistoryModal.tsx:133` (`No Versions Found for This Object.` has a trailing period), and `CorsRulesTable.tsx:127` / `LifecycleRulesTable.tsx:137` (trailing periods in titles)
- **What:** these `Status` titles break the title-case convention the Juno docs ask for, or repeat the generic default body.
- **How to fix:** an audit pass over `Status` titles in `packages/aurora/src/client` that brings them to "No X Found" title case with specific bodies, then a `check-i18n` run.
- **Why not in this plan:** they are in other domains (storage), outside epic #1327 and this issue.

Relevant files (absolute):
- packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRBACPolicies.tsx
- packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRBACPolicies.test.tsx
- packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx
- packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.test.tsx
- packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/SecurityGroupDetailsView.test.tsx
- packages/aurora/src/locales/{en,de}/messages.{po,ts}
- .changeset/ (new file)