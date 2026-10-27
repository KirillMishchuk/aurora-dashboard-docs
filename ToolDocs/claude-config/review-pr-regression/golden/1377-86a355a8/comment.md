## Update — 2026-10-26, head `86a355a8`

_Reviewed at head [`86a355a8`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377/commits/86a355a8d6da94478e77c0869d9720efe6823e2a) · base `main` at `af14a6a0` · <TIME>_

### ⚖️ &nbsp; Verdict

Recommendation: **🟡 Approve with process to-dos** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Still open from the earlier review:** P1

### Fixed since last analysis

- CR1 — portsRouter.list now follows `ports_links` next pages (visited-guarded loop) and returns the full list.
- CR3 — The route loader is gone; only the component's `useQuery` fetches the port.
- P2 — The description now covers the `?tab=` search param on the router details route.
- I1 — Copy now reads 'Sign in again to continue.'
- I2 — `PopupMenu` now has a `PopupMenuToggle` wrapping the icon Button.
- I3 — `gap="1"` is gone; PortDetailsView uses `0.5`, `2` and `6`, which B.3 allows.
- I4 — Status is now the 2nd column, right after Name / ID.
- I5 — Routers doc now says lookups are chunked into requests of at most 50 IDs.
- I6 — Error tables in the ports doc carry the `: {Neutron message}` suffix again.
- I7 — The `useEffect` is gone; `PageInput` is keyed on `currentPage` instead.
- I8 — `zod` is now imported right after the router import, before the Lingui imports.

**Partly fixed**

- CR2 — 403 is now a page-level info Message on both details and list. 401 is still not a redirect: the details page shows a 'Sign in' error page (I9) and the list falls into the generic error boundary with the raw BFF message (I11).

**Still open**

- P1 — PR is still a draft.

**No longer reviewed**

- CR4 — Merge conflicts are no longer part of this review; GitHub shows them.

### 🔧 &nbsp; Required Changes

None.

### 💡 &nbsp; Improvements

| #   | Severity | Category | Precedent | Issue                                                                                             | Location                                                                                                    |
| --- | -------- | -------- | --------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| I9  | 🟢 Low   | UI/UX    | —         | Port details still renders a 401 inline with a Sign in button to `/` instead of redirecting (B.6) | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:75`                  |
| I10 | 🟢 Low   | UI/UX    | —         | Status column renders the raw status string instead of a `Badge` (B.1)                            | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51` |
| I11 | 🟢 Low   | UI/UX    | —         | Ports list handles only 403; a 401 or other error shows the raw BFF `error.message`               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`   |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I9 — 401 on the port details page is an inline error page, not a redirect to Sign-in** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:75`
The CR2 fix turns `UNAUTHORIZED` into a `RouteIdLevelDefaultError` with code 401 and a button that navigates to `/`, at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:68`:

```tsx
if (errorCode === "UNAUTHORIZED") {
  return (
    <RouteIdLevelDefaultError
      code={401}
      errorTitle={t`Session Expired`}
      errorDescription={t`Your session has expired. Sign in again to continue.`}
      action={
        <Button variant="primary" onClick={() => navigate({ to: "/" })}>
          <Trans>Sign in</Trans>
        </Button>
      }
    />
```

B.6 lists "a 401/403 handled inline instead of via redirect" as a Reject and asks for a redirect to Sign-in that remembers the target and returns there after auth. Here the user lands on `/` and loses the port they were looking at; the comment above the branch also describes behaviour the code doesn't have.
_Fix:_ Redirect to the sign-in route with the current location as the return target (the way `_auth.tsx` does for a missing session) instead of rendering the error page, and update the comment.

**I10 — Port status is plain text in the list** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51` renders `port.status` as text. B.1 maps status indicators to `Badge`; the delta moved this cell to the 2nd column, so it now sits prominently as unstyled text (`ACTIVE`, `DOWN`, `BUILD`).
_Fix:_ Render the status as a `Badge` with a variant per status (e.g. success for `ACTIVE`, danger for `ERROR`/`DOWN`); the router list can follow in the same or a later PR.

**I11 — Ports list shows the raw error message and no Sign in path on 401** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`
`createPortsPromise` converts only `FORBIDDEN` into the info Message; everything else, including `UNAUTHORIZED`, is rethrown:

```tsx
// 403 is an expected "no access" state, not a failure: render it as a page-level info message
// (B.6) rather than letting it reach the error boundary.
if (err instanceof TRPCClientError && err.data?.code === "FORBIDDEN") {
  return { ports: [], forbidden: true }
}
throw err
```

The error boundary then prints `error.message` as the body at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`, so an expired session shows the BFF's text and no way to sign in. CR2 of the earlier review covered the list error as well; mark-karnaukh-extern-sap confirmed it in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6293554974 and listed it as fixed in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006, but only the details page got the 401 handling.
_Fix:_ Handle `UNAUTHORIZED` in the list the same way as the details page (ideally a redirect to Sign-in, see I9) and show a generic translated message instead of `error.message` for the remaining errors.

</details>

### 🗨️ &nbsp; Review comments not taken up

Raised in the review discussion, checked at this head and not counted as findings:

| Raised by                                                                                                                | Claim                                                                                                                                                                                                                                                                                          | Why not a finding                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| mark-karnaukh-extern-sap [comment](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006) | Client-side search duplicates the BFF filterPortsBySearchTerm field list by hand (comment says 'mirroring'), and the BFF still accepts and runs search/sort/limit params that the UI no longer uses. The two implementations can drift and the BFF params are dead code for the only consumer. | PortsList.tsx:59 duplicates the BFF search field list, and the BFF params are unused by the UI. It is a deliberate perf decision the author raised as an open question, and a code-quality opinion with no concrete defect. |

### What changed

<details>
<summary><strong>What was done</strong></summary>

This update covers `512f01b1` to `86a355a8`. The PR is still a draft. CI on the head commit: 18 of 22 checks pass, 4 are skipped, none failed or pending.

**Ports list moves to client-side sorting and search.** The list now fetches the full port list once per project/network and sorts, searches and paginates it in the browser. Sort, search and page changes no longer send a request, and the `useDeferredValue`/stale-result handling is gone. The sort keys offered shrink to `name`, `status` and `device_owner`. Search filtering now runs on the locally typed text on every keystroke, while the URL is still updated with a debounce. The BFF `list` procedure still accepts `sort_key`, `sort_dir` and `searchTerm`, but the page no longer uses them.

**Routers get the same treatment in places the findings did not cover.** The Routers BFF `list` now also follows Neutron pagination through `routers_links`, with a new test. In the Routers list, the Status column moves to second position, the row action menu gets a visible `PopupMenuToggle` button, and a 403 now shows an info message "Insufficient Permissions" instead of the "Failed to Load Routers" error. The Router tests are updated to match.

**Port details page title is now static.** With the loader removed, the browser tab title is always "Port Details" and no longer shows the port name.

**Pagination plumbing.** `nextPageUrl` is a new shared helper in `requestHelpers.ts`, and `PortListResponseSchema` and `RouterListResponseSchema` gain an optional `*_links` field. Both list loops use a `visited` set as a guard against a non-advancing `next` link.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

Each list loop reuses only the query string of Neutron's absolute `next` href, against the known relative base path:

```ts
export const nextPageUrl = (baseUrl: string, links?: Array<{ rel: string; href: string }>): string | undefined => {
  const href = links?.find((link) => link.rel === "next")?.href
  if (!href) return undefined
  const queryIndex = href.indexOf("?")
  return queryIndex === -1 ? baseUrl : `${baseUrl}${href.slice(queryIndex)}`
}
```

The client-side list pipeline filters, then sorts, then pages:

```tsx
const visiblePorts = useMemo(
  () => sortPorts(filterPorts(ports, localSearchTerm), sortSettings.sortBy, sortSettings.sortDirection),
  [ports, localSearchTerm, sortSettings.sortBy, sortSettings.sortDirection]
)
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- The Routers BFF `list` contract changes: it now issues several requests when Neutron paginates. `packages/aurora/docs/0010_routers_bff.md` was updated for this.
- Search, sort and pagination on the Ports list now run on the full list in the browser. For projects with many ports, the first load is heavier, and `filterPorts` in `PortsList.tsx` duplicates the BFF's `filterPortsBySearchTerm`, so the two must be kept in sync.
- `sort_key`, `sort_dir` and `searchTerm` on `ports.list` (`packages/aurora/src/server/Network/types/port.ts:115`) are now unused by the only client, but remain in the contract and docs.
- Router list and Router tests were edited as part of this update, although the Routers feature is outside the Ports scope in the PR description. The description does not mention the Routers list changes (Status column order, action toggle, 403 info message, pagination).

</details>
