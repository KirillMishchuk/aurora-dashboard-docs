---
type: pr-report
date: 2026-08-18
status: merged
pr: [1184]
author: mark-karnaukh-extern-sap
branch: mark-right-align-primary-buttons
---
# PR #1184: fix(portal): right-align primary buttons / fix button order (#1183)

**Author:** mark-karnaukh-extern-sap · **Status:** merged 2026-08-18 (commit `9cdf0ae`; created 2026-08-18)
**Branches:** `mark-right-align-primary-buttons` → `main` · **Files:** 2 (+9/-3)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1184

## What was done

Closes issue #1183 (AC: the primary create action must be the last button, and all primary buttons must be right-aligned). In the Swift Objects toolbar (Zone 1), the "Create Folder" (primary) and "Upload Object" buttons were in the order "Create Folder → Upload Object" — the primary button was not last. The PR changes the order to "Upload Object → Create Folder" and touches nothing else: the JSX itself, the handlers and the `Stack` structure are identical; only two adjacent lines swapped places.

```tsx
// SwiftObjects/index.tsx:424-429 (after the change)
<Button className="whitespace-nowrap" onClick={() => setUploadModalOpen(true)}>
  <Trans>Upload Object</Trans>
</Button>
<Button variant="primary" className="whitespace-nowrap" onClick={() => setCreateFolderModalOpen(true)}>
  <Trans>Create Folder</Trans>
</Button>
```

The changeset `.changeset/open-maps-burn.md` (`patch`, `@cobaltcore-dev/aurora`) ships in the same PR — unlike #1181, here it was added right away rather than in a separate late commit.

## What it affects

The PR description claims that `SwiftContainers` already satisfies the issue's requirements — verified against the code (`Swift/Containers/index.tsx:295-311`): there is only one button there ("Create Container", `variant="primary"`) in a `Stack distribution="end"`, so it is trivially last and rightmost. The claim is correct.

Beyond that, the issue is worded broadly ("all primary buttons are right-aligned consistently across the layout"), even though its title is tagged `[Bug](Swift)`, so it was worth checking whether the same "primary button is not last" pattern remained anywhere else in the app. I went through all similar toolbars (Zone 1 "sort + create") in Compute/Network/Storage: `Flavors/List.tsx`, `Images/List.tsx`, `FloatingIpsList.tsx`, `SecurityGroupsList.tsx`, `Ceph/Buckets/index.tsx` — everywhere there is exactly one primary button ("Create ...") in a `Stack distribution="end"`, trivially last and rightmost. The only other place with *two* buttons in one zone is the Ceph counterpart of the same screen, `Ceph/Objects/ObjectBrowserView.tsx:644-659` — there the order is already correct: `Upload Object` first, `Create Folder` (primary) last. It looks like the Swift version was copied from exactly this Ceph pattern, but the button order got swapped during copying — this PR simply brings Swift in line with the reference that already exists in Ceph. No other places with the same problem were missed.

## Review

No issues with confidence ≥80 found. The change is minimal and precise (two lines swapped, no other logic touched), the changeset is present and matches the scope (`patch`), and the comparison with the Ceph counterpart confirms both the correctness and the completeness of the fix. The existing tests (`index.test.tsx`) locate the buttons via `getByRole("button", { name: ... })` — they do not depend on DOM order and do not check it; no new test for the button order itself was added, but this is below the threshold (CLAUDE.md does not require tests for visual order, and the buttons' behavior has not changed).

---
Analyzed: 2026-08-18 · commit `dd74644`
