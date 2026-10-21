---
type: pr-report
date: 2026-10-21
status: open
pr: [1390]
issue: []
author: TilmanHaupt
branch: til-img-2010
---

# PR #1390: chore(portal): image UX improvements and validation tightening

**Author:** TilmanHaupt · **Status:** open · **Base:** `main` ← `til-img-2010`
**Size:** 28 files, +624 / −149 · **Created:** 2026-10-20 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1390)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

A focused, well-tested polish pass over the Images screens: stricter Min Disk / Min RAM input, a dedicated Glance error path for metadata edits, "- -" placeholders and theme-token cleanup. The one code problem that blocks is that the new metadata error mapping labels **every** 403 as "This property is reserved", so a plain permission or property-protection denial gets a misleading explanation. The changeset edit also collides with the open release PR #1384. CI is green. Acceptance could not be verified: the PR links no issue, and the epic #1332 supplied for it carries no acceptance criteria.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category | Issue                                                                                   | Location                                                         |
| --- | ----------- | -------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| CR1 | 🟡 Moderate | Bug      | Every 403 on image metadata update is shown as "This property is reserved"              | `packages/aurora/src/server/Compute/helpers/imageHelpers.ts:328` |
| CR2 | 🟡 Moderate | Process  | Edits a changeset that the open release PR #1384 deletes — modify/delete conflict       | `.changeset/fix-image-ux-improvements.md`                        |
| P1  | —           | Process  | PR links no issue; acceptance criteria not verifiable                                   | PR body                                                          |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Any 403 becomes "reserved property"** · Bug · `packages/aurora/src/server/Compute/helpers/imageHelpers.ts:328`
`classifyMetadataUpdateError` returns the `IMAGE_METADATA_RESERVED` sentinel whenever `statusCode === 403`, before the `isReadOnly` text check is even relevant; the client turns that into "This property is reserved and cannot be modified." (`packages/aurora/src/client/utils/useErrorTranslation.ts:10`). The Glance [Update image](https://docs.openstack.org/api-ref/image/v2/#update-image) reference lists several distinct 403 causes — read-only base properties and `os_glance*` names (genuinely reserved), but also "An attempt to create or modify image properties for which you do not have permission to do so … This depends upon how property protections are configured", and deleting the only image location. A user blocked by a property-protection rule (or by image policy) is told the property is reserved, which is false and sends them hunting for the wrong cause. Before this PR the generic mapper said "Access forbidden - cannot update image…". The behaviour is locked in by `packages/aurora/src/server/Compute/helpers/imageHelpers.test.ts:969` ("should emit IMAGE_METADATA_RESERVED on 403", no message). Copilot raised this inline on `imageHelpers.ts:329`; the author replied "This is here indeed different", with no code change.
_Fix:_ Return `IMAGE_METADATA_RESERVED` only when the cleaned reason matches the read-only/reserved pattern; map other 403s to a separate sentinel (e.g. `IMAGE_METADATA_FORBIDDEN` → "You are not permitted to modify this property or image.") and update the 403 test accordingly.

**CR2 — Changeset collides with release PR #1384** · Process · `.changeset/fix-image-ux-improvements.md`
The PR appends 13 bullets to `fix-image-ux-improvements.md`, a changeset that already exists on `main` (from #1379) rather than adding its own. The open Changesets release PR #1384 consumes and deletes that file; `git merge-tree` of the two heads reports a modify/delete conflict on it. Whichever merges second has to resolve it, and if #1384 goes first this PR is left with no changeset for its own changes (or its bullets get folded into an already-published changelog).
_Fix:_ Move the new bullets into a new `.changeset/<name>.md` (patch for `@cobaltcore-dev/aurora`) and leave the existing file untouched.

**P1 — No linked issue** · Process · PR body
The PR body links no issue. Epic #1332 ("All Image issues") was supplied as context, but its body has no acceptance criteria and all its sub-issues are closed, so there is nothing to grade the PR against.
_Fix:_ Link the tracking issue (or open one listing these review items) in the PR body.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category      | Issue                                                                                        | Location                                                                                                         |
| --- | ---------- | ------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| I1  | 🟢 Low     | Bug           | New update error handler drops the 413/415 mappings — they now surface as 500                | `packages/aurora/src/server/Compute/helpers/imageHelpers.ts:392`                                                 |
| I2  | 🟢 Low     | UI/UX         | "Project not found." asserts non-existence when the lookup only failed, and still blocks sharing | `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageMembersTable.tsx:92` |
| I3  | 🟢 Low     | UI/UX         | `SizeDisplay` still renders "N/A" despite "replace remaining N/A"                             | `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/SizeDisplay.tsx:8`        |
| I4  | 🟢 Low     | UI/UX         | Shared `TwoColumnDescriptionList` placeholder also changes Floating IP / Security Group pages, unannounced | `packages/aurora/src/client/components/TwoColumnDescriptionList.tsx:15`                                          |
| I5  | 🟢 Low     | Accessibility | New icon-only close control has no `aria-label`                                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:527` |
| I6  | 🟢 Low     | UI/UX         | New error strings use "Please" and say "positive" while 0 is accepted                         | `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:122` |
| I7  | ⚪ Trivial | Docs          | Keydown comment contradicts the badInput check added in the same PR                          | `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:188` |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — 413/415 regress to INTERNAL_SERVER_ERROR** · Bug · `packages/aurora/src/server/Compute/helpers/imageHelpers.ts:392`
`imageRouter.ts:590` switched from the generic `mapErrorResponseToTRPCError` to `ImageErrorHandlers.update`, whose switch handles only 400/403/404/409 and sends everything else to `INTERNAL_SERVER_ERROR`. The generic mapper turned 413 into `PAYLOAD_TOO_LARGE` and 415 into "Unsupported media type"; Glance documents both for PATCH ("Error response codes: 400, 401, 403, 404, 409, 413, 415"). Rare for a small JSON-patch, but a too-large property set now reads as a server failure.
_Fix:_ Add `case 413` / `case 415` branches (the sibling `upload` handler at `imageHelpers.ts:367-376` already has them), or fall back to the generic mapper in `default`.

**I2 — Sharing message overstates what the lookup proved** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageMembersTable.tsx:92`
`project.getProject` returns `null` not only for a missing project but for an un-encodable ID and for any failed or unparseable Keystone call (`packages/aurora/src/server/Project/routers/projectRouter.ts:274`, `:277-281`, `:285`). The PR shortened the message from "Project not found or you don't have access to it." to "Project not found.", so an existing-but-unreadable project is now declared non-existent, and the `if (!project)` branch still blocks the add — contrary to the changeset's "sharing to projects you can't access is allowed" and the code's own comment "don't block if check fails". The blocking itself predates this PR; the wording is new. Copilot raised this inline; the author replied "Comment wrong" without elaborating.
_Fix:_ Either keep the softer wording, or treat a `null` result as inconclusive (warn, don't block) and let Glance validate the member.

**I3 — "N/A" left in `SizeDisplay`** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/SizeDisplay.tsx:8`
The PR body and changeset say "Replace remaining 'N/A' placeholders with '- -' across image rows, details, and modals", but `SizeDisplay` (used in the image row, details view and Delete modal) still returns `<span>N/A</span>`, asserted by `SizeDisplay.test.tsx:9` and `ImageDetailsView.test.tsx:145`. An image without a size shows "N/A" next to "- -" placeholders.
_Fix:_ Return "- -" there and update both tests.

**I4 — Placeholder change leaks into network detail pages** · UI/UX · `packages/aurora/src/client/components/TwoColumnDescriptionList.tsx:15`
`TwoColumnDescriptionList` is shared: besides `ImageDetailsView`, it renders `FloatingIpDetailsView.tsx:88,95,102` and `SecurityGroupBasicInfo.tsx:26`. Those pages now show "- -" for `null`/`undefined`/`""`/`[]` values where they rendered blank — a visible change outside Images that neither the PR body nor the changeset mentions.
_Fix:_ Mention it in the description/changeset and spot-check those two pages, or make the placeholder opt-in if it isn't wanted there.

**I5 — Close icon lacks an accessible label** · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:527`
The text "Remove" button was replaced by `` <Icon icon="close" … title={t`Remove`} onClick=…/> ``. `copilot-instructions.md` B.14: "Reject: … any icon-only button without `aria-label`". In Juno 9.4.0 the `title` probably yields an accessible name, so the impact is small, but the rule is explicit.
_Fix:_ Add `` aria-label={t`Remove`} ``.

**I6 — "Please" and "positive" in the new error text** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:122`
The new badInput branch (`:122`, `:124`) adds two uses of `` t`Please enter a valid positive number` ``; the Quick Reject checklist rejects strings using "Please". The wording is also inaccurate: `/^\d+$/` accepts 0. The same string already exists at `:146`/`:148`, so this is precedent rather than a new msgid.
_Fix:_ Use e.g. `` t`Enter a whole number of 0 or more` `` in all four places.

**I7 — Contradictory comment** · Docs · `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:188`
The `handleNumericKeyDown` comment says non-digit input "leaves the field in a badInput state the change handler can't reliably see", while the same PR makes the change handler check `e.target.validity.badInput` first (`:118-120`). The pre-existing "Invalid number input - set error immediately" (`:144`) now sits under a different condition.
_Fix:_ Reword the keydown comment to "block at the keystroke so the field never enters badInput" and tighten `:144`.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

A collection of follow-ups from UI review of the Images feature (epic #1332), all in `@cobaltcore-dev/aurora`:

- **Server — metadata update errors.** Image PATCH failures used to go through the generic error mapper and surface raw (often HTML) Glance text. A dedicated `ImageErrorHandlers.update` now classifies 400/403 into two sentinel codes — `IMAGE_METADATA_RESERVED` and `IMAGE_METADATA_INVALID: <cleaned reason>` — that the client translates.
- **Client — Create Image validation.** Min Disk / Min RAM accept only digits (non-digit keystrokes are blocked, `badInput` and scientific notation like `1e5` are rejected, empty means 0), and Create stays disabled while any field, optional ones included, has an error. Fields are reordered so Disk/Container Format sit next to the file, raw palette classes give way to theme tokens, and the selected file is shown in a neutral Juno `Box` with a close icon.
- **Client — placeholders and polish.** Empty values show "- -": in the shared `TwoColumnDescriptionList`, in image rows/details, and as the name fallback in the Activate/Deactivate/Delete modals (replacing "N/A" / "Unnamed"). Bulk-modal restriction notices use the default text size and colour; the images loading indicator becomes a full-width grid row; Manage Access uses a `Status` empty state and a shorter "Project not found." error.
- **Housekeeping.** `.gitignore` gains `tmp/` and `.playwright-mcp/`; 13 bullets are appended to the existing (unreleased) changeset `.changeset/fix-image-ux-improvements.md` (patch); catalogs regenerated.

CI is green on `3ef411e`. The PR body omits two items the changeset lists (the `Status` empty state in Manage Image Access and the `Box`-with-close-icon file row) and doesn't say that the metadata-error explanation is done by a new server-side handler.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Server: classifying metadata update failures.** The router's PATCH now delegates to the new handler:

```ts
          .catch((error) => {
            throw ImageErrorHandlers.update(error, imageId)
          })
```
(`packages/aurora/src/server/Compute/routers/imageRouter.ts:589`)

`ImageErrorHandlers.update` sends 400 and 403 to the classifier and maps 404/409 to their own messages; everything else is `INTERNAL_SERVER_ERROR`:

```ts
  update: (response: { statusCode?: number; message?: string }, imageId: string) => {
    switch (response.statusCode) {
      case 400:
      case 403:
        return classifyMetadataUpdateError(response.statusCode, response.message)
```
(`packages/aurora/src/server/Compute/helpers/imageHelpers.ts:392`)

The classifier first cleans the Glance body with `extractGlanceReason` (strips tags, a few entities, "400 Bad Request"/"403 Forbidden" lines and the "Failed validating …" trailer), then decides:

```ts
  const reason = extractGlanceReason(rawMessage)
  const isReadOnly = /read[\s-]?only|forbidden to (?:modify|update)|cannot be (?:modified|updated|changed)/i.test(
    reason
  )

  if (statusCode === 403 || isReadOnly) {
    return new TRPCError({ code: "FORBIDDEN", message: "IMAGE_METADATA_RESERVED" })
  }
```
(`packages/aurora/src/server/Compute/helpers/imageHelpers.ts:323`)

Non-reserved rejections become `BAD_REQUEST` with `IMAGE_METADATA_INVALID: ${reason}` (`imageHelpers.ts:332-335`).

**Client: decoding the sentinels.** `useErrorTranslation` gains a branch ahead of its flavor-code switch:

```ts
    if (errorCode === "IMAGE_METADATA_RESERVED") {
      return t`This property is reserved and cannot be modified.`
    }
    const INVALID_PREFIX = "IMAGE_METADATA_INVALID"
    if (errorCode === INVALID_PREFIX || errorCode.startsWith(`${INVALID_PREFIX}: `)) {
      const reason = errorCode.slice(INVALID_PREFIX.length).replace(/^:\s*/, "").trim()
      return reason ? t`The image service rejected this change: ${reason}` : t`The image service rejected this change.`
    }
```
(`packages/aurora/src/client/utils/useErrorTranslation.ts:9`)

The Glance reason is interpolated as plain text into a translated sentence; it is not itself translated.

**Create Image: numeric fields.** The change handler checks `badInput` first, treats empty as 0, and accepts only plain digits:

```tsx
      if (value.trim() === "") {
        setProperties((prev) => ({ ...prev, [name]: 0 }))
        setErrors((prev) => {
          const newErrors = { ...prev }
          delete newErrors[name]
          return newErrors
        })
        return
      }
      // Accept only plain non-negative integers. parseInt is too lenient — it truncates
      // scientific notation (e.g. "1e5" -> 1), and type="number" treats "1e5" as valid — so
      // validate the raw string ourselves instead of relying on parseInt / validity.valid.
      const isNonNegativeInteger = /^\d+$/.test(value.trim())
```
(`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:130`)

A keydown guard keeps non-digits out in the first place, while letting editing keys and shortcuts through:

```tsx
    const isSingleChar = e.key.length === 1
    const isModifierCombo = e.ctrlKey || e.metaKey || e.altKey
    if (isSingleChar && !isModifierCombo && !/^[0-9]$/.test(e.key)) {
      e.preventDefault()
    }
```
(`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:192`)

and `isFormValid` now also requires an empty error map:

```tsx
    // Also block submission while any field (including optional ones) has a validation error
    Object.keys(errors).length === 0
```
(`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:89`)

The selected file is rendered as a Juno `Box` with a close icon instead of the old success styling and "Remove" text button:

```tsx
                  <Box className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-theme-default">{selectedFile.name}</span>
                    <Icon
                      icon="close"
                      size="18"
                      title={t`Remove`}
                      disabled={isLoading}
```
(`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/CreateImageModal.tsx:525`)

**Shared placeholder.** `TwoColumnDescriptionList` renders "- -" for empty values:

```tsx
// Placeholder shown when a detail value is empty (null, undefined, "", or [])
const EmptyValue = () => <>- -</>

const isEmptyValue = (value: DetailListItem["value"]): boolean =>
  value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0)

const renderValue = (value: DetailListItem["value"]) => (isEmptyValue(value) ? <EmptyValue /> : value)
```
(`packages/aurora/src/client/components/TwoColumnDescriptionList.tsx:14`)

Image rows, details and the action modals use the literal `"- -"` in place of `` t`N/A` `` / `` t`Unnamed` ``.

**Manage Access.** The project pre-check keeps its logic; only the message changed:

```tsx
        const project = await utils.project.getProject.fetch({ projectId: trimmedMemberId })
        if (!project) {
          newErrors.memberId = t`Project not found.`
        }
```
(`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageMembersTable.tsx:90`)

and the empty member list becomes a `Status` (`ImageMembersTable.tsx:251-255`, title "No Project Access").

**Images list loading.** The loading state is now one full-width row inside the real grid:

```tsx
        <DataGrid columns={hasAnyBulkAction ? 9 : 8} className="images">
          <DataGridRow>
            <DataGridCell colSpan={hasAnyBulkAction ? 9 : 8}>
              <Status status="progress" title={t`Loading...`} />
            </DataGridCell>
          </DataGridRow>
        </DataGrid>
```
(`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageListView.tsx:595`)

Tests: new cases in `CreateImageModal.test.tsx` (scientific notation, badInput, keystroke blocking, disabled-on-error), `EditImageMetadata.test.tsx` (reserved/invalid messages), `imageHelpers.test.ts` / `imageRouter.test.ts` (classification), `TwoColumnDescriptionList.test.tsx` (placeholder), plus updated expectations in `ImageDetailsView.test.tsx` and `DeleteImageModal.test.tsx`.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **`TwoColumnDescriptionList` (shared component).** Consumers outside Images: `packages/aurora/src/client/routes/_auth/projects/$projectId/network/floatingips/$floatingIpId/-components/-details/FloatingIpDetailsView.tsx:88,95,102` and `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupBasicInfo.tsx:26`. They inherit the "- -" placeholder for empty values (I4).
- **`useErrorTranslation` (shared hook).** Also used by the Flavors screens and `EditImageMetadataModal`. The new branches only match `IMAGE_METADATA_*` codes, so flavor codes are unaffected. Add, edit and delete in `EditImageMetadataModal` all go through the same `compute.updateImage` PATCH, so all three now get the sentinel messages on 400/403; other image procedures keep their old mappers.
- **Server.** `ImageErrorHandlers.update`, `classifyMetadataUpdateError` and `extractGlanceReason` are new exports of `imageHelpers.ts`, used only by the image router. The `compute.image` update procedure keeps its key and input; its error *messages* change from prose to sentinel strings, which matters only to a client that matched the old text — in-repo, only the Images UI consumes them.
- **Left inconsistent.** `SizeDisplay.tsx:8` still renders "N/A" (I3). The action modals fall back to "- -" for an empty name, while the table row and the Delete modal body still fall back to the image ID (from #1379).
- **Contract.** Internal only: no change to `AuroraApp` props, slots, public server exports or permission keys.
- **Other open PRs.** Compiled catalogs (`packages/aurora/src/locales/*/messages.ts`) conflict with #1383, #1385 and #1377 (routine regeneration); the changeset conflicts with release PR #1384 (CR2).

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open Compute → Images. While loading, the "Loading..." indicator spans the whole grid width.
2. In the list, images without a value in a column show "- -", not "N/A".
3. Open Create Image. Check the field order (file, then Disk/Container Format, then the rest) and the dropzone and progress colours in both light and dark theme.
4. Pick a file: it appears in a neutral box with an X; click X to remove it, then pick a file again.
5. Fill the required fields, set Min Disk 10 and Min RAM 512, create the image. It appears in the list.
6. Open its details: empty fields show "- -".
7. Edit Metadata: try to change a read-only/reserved property (e.g. an `os_glance_*` key) and confirm "This property is reserved and cannot be modified."; submit an invalid value and confirm "The image service rejected this change: …" with clean text and no HTML.
8. Manage Image Access with no members: the "No Project Access" empty state shows. Add a valid project ID — it is added.
9. Select several images and open bulk Activate / Deactivate / Delete: the restriction notices use normal text size and colour.
10. Open a Floating IP and a Security Group detail page and check the new "- -" placeholders look right there.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Min Disk / Min RAM: type `e`, `-`, `.`, `+` — nothing is entered (`CreateImageModal.tsx:194`); Ctrl/Cmd+V, Backspace and arrows still work.
- Paste `1e5` — error shown, Create disabled (`CreateImageModal.tsx:142-150`); paste `-5` / `1.5` — same.
- Clear the field — value resets to 0 and any error clears (`CreateImageModal.tsx:130-137`); the field immediately shows "0".
- Very long digit string (20+ digits) — passes the regex; check what Glance returns on submit.
- Error on an optional field while required ones are valid — Create stays disabled (`CreateImageModal.tsx:90`); fixing it re-enables Create.
- Remove a file, then re-pick the **same** file — the file input isn't reset, so check it is actually re-selected.
- X icon while uploading — disabled (`CreateImageModal.tsx:531`).
- Metadata edit as a user whose role is denied by a property-protection rule (Glance 403 that is not a reserved name) — currently shows "reserved and cannot be modified" (CR1, `imageHelpers.ts:328`).
- Metadata PATCH returning 413 or 415 — currently surfaces as an internal error (I1, `imageHelpers.ts:407-411`).
- Metadata PATCH 400 with an HTML body — cleaned reason only; 400 with empty body — "The image service rejected this change."
- Manage Access with a project ID that exists but the user can't read in Keystone — blocked with "Project not found." (I2, `ImageMembersTable.tsx:91-92`).
- Image with no size — still "N/A" (I3, `SizeDisplay.tsx:8`).
- Image with an empty name in Activate / Deactivate / Delete modals — "- -" as the name, ID shown separately.
- Detail value of `null` vs `[]` vs `""` — all "- -" (`TwoColumnDescriptionList.tsx:17-18`).
- German locale — new strings ("No Project Access", the reserved / rejected messages, "Project not found.") have no German translation yet and fall back to English.

</details>

---

_Analyzed 2026-10-21 · commit `3ef411e` · read-only · CI from PR API · acceptance graded against #1332 supplied by the reviewer · skill: review-and-comment-pr_
