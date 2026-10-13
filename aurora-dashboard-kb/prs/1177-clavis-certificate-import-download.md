---
type: pr-report
date: 2026-08-19
status: merged
pr: [1177]
author: vlad-schur-external-sap
branch: clavis-ui-ux-changes-with-downloading
---
# PR #1177: feat(clavis): different changes(api/ui-ux) with downloading functionality

**Author:** vlad-schur-external-sap · **Status:** merged 2026-08-19 (commit `35095b4`; commits 2026-08-13 – 2026-08-19) — **report version 2**
**Branches:** `clavis-ui-ux-changes-with-downloading` → `main` · **Files:** 30 (+1204/-845 against current `main`, base `9cdf0ae`), of which `pnpm-lock.yaml` is a technical regeneration for the `@cloudoperators/juno-ui-components` upgrade and is not analyzed below
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1177

> Access to the GitHub REST/GraphQL API is blocked from this session (`gh`/`gh api` and direct `curl` to `api.github.com`/`github.com/.../pull/1177.diff` return 403 "GitHub access to this repository is not enabled for this session… Use add_repo…"). The PR title, author, status, branches and description were obtained via `WebFetch` of the PR's HTML page itself — a working source for these fields, but not confirmed by a second method. All code, the diff and the commit history were verified via an anonymous `git clone` + `git fetch origin refs/pull/1177/head` (public repository; the git protocol is not subject to the same restriction) — a reliable source for everything else. This is an update of the report from 2026-08-14 (commit `0a1b61c`): since then, 3 new commits were added to the PR (13:25→10:22, 2026-08-19) plus one merge of `main` that pulled in #1176/#1181/#1184 — those are unrelated to the PR and are not analyzed here. `git diff main...pr-1177-head` (current `main`) is the source of truth for the whole report, as `document-pr` prescribes.

## What was done

The PR continues the series of Clavis (Private Certificate Authority) improvements in `packages/aurora/src/client/routes/.../services/pca/` with seven substantive commits by a single author (2026-08-13→2026-08-19) plus three merge commits of `main`:

1. **`e3f051f` "remove unexpected states as its not available on the client"** — removes `"UNEXPECTED"` from `CertificateAuthorityStateSchema` (server) and from both UI state mappings, and deletes the corresponding tests.
2. **`d8a2186` "implement downloading"** — implements PEM/CSR download via `DetailsInfo`, bumps `@cloudoperators/juno-ui-components` to `9.3.0` (needed for `codeBlockFooter`).
3. **`3485002` "update import-issue validation and upload logic"** — makes `parseCsrInfo` synchronous, adds certificate chain parsing/validation, narrows the import file upload to `.json`.
4. **`3a91742` "change btn possition for creating certificates"** — moves the "Issue Self-Signed Certificate" button from `PcaDetailsView` to `PcaCertificatesListContainer` (a pure relocation; the visibility condition did not change).
5. **`288977d` "fix(clavis): ai comments and typos"** (2026-08-19, 09:25) — despite its name, a substantive commit: renames the label `"Subject"` → `"Subject Information"` (everywhere — `parseCsrInfo.ts`, `PcaDetailsView.tsx`, `PcaListContainer.tsx`), extracts a separate strict `isValidCsr` from `isValidPem` (rejects the input if it is a certificate rather than a CSR — previously `IssueEndEntityCertificateModal` validated the CSR field via `isValidPem`, which accepted both a CSR and a certificate), adds a "Certificate Imported" toast on import, and adds `getById` invalidation after CA self-signing.
6. **`f9dc694` "fix(clavis): get-by-id invalidation and tests for parsing and importing"** (2026-08-19, 09:56) — narrows the `getById` invalidation after certificate import from "invalidate all `getById` queries" to "invalidate specifically `{project_id, certificate_authority_id}` of this CA".
7. **`de468bd` "refactor(clavis): replace creating and awaiting icons"** (2026-08-19, 10:22, the most recent commit) — replaces the `CREATING`/`AWAITING_CERTIFICATE` state icons with `Spinner`/`Icon` from `juno-ui-components` instead of `react-icons/md`, introducing a regression along the way — see "Review".

What the PR description claims ("Fixed CSR/PEM validation and parsing, make parsing sync", "Added PEM downloads", "Removed the UNEXPECTED state", a link to #1160) matches the diff, with the same caveat as in the previous version of the report: narrowing the file upload to `.json` is not mentioned explicitly. Not a single item of the checklist in the PR description is ticked (all 6 checkboxes `- [ ]` are unchecked).

## How it is implemented

### `getById` invalidation after CA mutations — two targeted fixes in this round

Before today's commits, `IssueSelfSignedCertificateModal` invalidated only the certificate list, and `ImportExternallySignedCertificateModal` invalidated the whole `getById` cache with no filter by CA:

```tsx
// IssueSelfSignedCertificateModal.tsx:20-25
const { isPending, ...createCertificateMutation } = trpcReact.services.pca.createCertificate.useMutation({
  onSettled: () => {
    utils.services.pca.listCertificates.invalidate()
    utils.services.pca.getById.invalidate({ project_id: projectId, certificate_authority_id: pca.id })
  },
})
```

```tsx
// ImportExternallySignedCertificateModal.tsx:36-42
const { isPending, ...importMutation } = trpcReact.services.pca.import.useMutation({
  onSettled: () =>
    utils.services.pca.getById.invalidate({
      project_id: projectId,
      certificate_authority_id: pcaId,
    }),
})
```

Both places now deliberately invalidate `getById` of the specific CA (`$pcaId/index.tsx:23,57` feeds `PcaDetailsView` exactly this query) — before the fix, the CA details page could keep the stale state badge and stale `DetailsInfo` contents after self-signing/import until a manual refresh. A real, well-justified bug fix, covered by updated tests.

### Toast notifications on delete and import

New file `PcaToastNotifications.tsx` (15 lines) — two builders in the same style as in other parts of the app (`ImageToastNotifications`, `ObjectToastNotifications`):

```tsx
// PcaToastNotifications.tsx:7-15
export const getPcaDeletedToast = (pcaName: string): ToastReturn => ({
  message: <Trans>Certificate Authority Deleted</Trans>,
  description: <Trans>Certificate Authority "{pcaName}" was successfully deleted.</Trans>,
})

export const getCertificateImportedToast = (): ToastReturn => ({
  message: <Trans>Certificate Imported</Trans>,
  description: <Trans>The externally signed certificate was successfully imported.</Trans>,
})
```

They are wired into `DeletePcaModal.tsx:49-50` and `ImportExternallySignedCertificateModal.tsx:59-60` right after a successful mutation, before `handleClose()`. Both strings are correctly wrapped in `<Trans>` and present in the `messages.po` diff.

### CSR vs certificate — separate validation instead of a shared `isValidPem`

```ts
// parseCsrInfo.ts:96-119
export const isValidPem = (pem: string) => {
  try {
    const sanitizedPem = cleanPem(pem)
    if (sanitizedPem.includes("-----BEGIN CERTIFICATE-----")) {
      parseCertificateChain(sanitizedPem)
    } else {
      new Pkcs10CertificateRequest(sanitizedPem)
    }
    return true
  } catch {
    return false
  }
}

export const isValidCsr = (pem: string) => {
  try {
    const sanitizedPem = cleanPem(pem)
    if (sanitizedPem.includes("-----BEGIN CERTIFICATE-----")) return false
    new Pkcs10CertificateRequest(sanitizedPem)
    return true
  } catch {
    return false
  }
}
```

`IssueEndEntityCertificateModal.tsx:9,32` now validates the CSR field via `isValidCsr` instead of `isValidPem` — a real narrowing: previously one could paste a full certificate into the "Paste CSR code" field and the form would consider it valid (`isValidPem` accepts both), now only a genuine CSR is accepted for this field. This is hidden under the uninformative commit name "ai comments and typos", even though it changes the form's validation behavior. A side effect is that `isValidPem` remains exported but has lost its only consumer (see "Review").

### CA state icons — switching to juno components instead of `react-icons/md`

```tsx
// PcaTableRow.tsx:34-42
const STATE_CONFIG = {
  CREATING: {
    text: t`Creating`,
    icon: <Spinner size="18" />,
  },
  AWAITING_CERTIFICATE: {
    text: t`Awaiting Certificate`,
    icon: <Icon icon="accessTime" size={20} color="#FBC02D" />,
  },
  ...
```

In the table (`PcaTableRow.tsx`) the text and the icon are separate fields, and `t\`Creating\`` is untouched. But on the details page the same replacement introduced a regression:

```tsx
// PcaDetailsView.tsx:45-56
const STATE_CONFIG = {
  CREATING: (
    <Badge variant="info">
      <Stack direction="horizontal" gap="1" alignment="center">
        <Spinner size="18" /> Creating
      </Stack>
    </Badge>
  ),
  AWAITING_CERTIFICATE: <Badge icon="accessTime" variant="warning" text={t`Awaiting Certificate`} />,
  READY: <Badge icon="checkCircle" variant="success" text={t`Ready`} />,
  FAILED: <Badge icon="error" variant="error" text={t`Failed`} />,
} as const
```

The consequences are analyzed in "Review"; this is the main finding of this version of the report.

## What it affects

The blast radius was checked for every changed/new symbol across the whole monorepo at `pr-1177-head`:

- **`isValidCsr`, `isValidCertificateChain`, `getCertificateImportedToast`, `getPcaDeletedToast`** — each is used by exactly one consumer within the same PR (`IssueEndEntityCertificateModal`, `ImportExternallySignedCertificateModal` ×2, `DeletePcaModal` respectively); there are no other usages in the repository.
- **`isValidPem`** — exported, but since commit `288977d` it has no consumers in the repository (verified with `git grep`); previously it was the only validator of the CSR field. Lint/typecheck won't catch this (no rule for unused *exports* is enabled in the package's ESLint config — there is only `no-unused-vars` for local variables).
- **`CertificateAuthorityStateSchema`/`CertificateAuthorityState`** — as in the previous version of the report: not re-exported from the package's public entry points (an internal type), but it validates real backend responses in `pcaRouter.ts` (`list`/`create`/`getById`/`import` all go through `parseOrThrow`, which throws `TRPCError({code: "PARSE_ERROR"})` for the whole call on a schema mismatch) — narrowing the enum remains the same open question as before (see "Review").
- **`apps/dashboard`** does not reference the `pca` code directly — the change is entirely internal to `packages/aurora`.
- New/renamed labels (`"Subject Information"`) are updated in sync in three places (`parseCsrInfo.ts`, `PcaDetailsView.tsx`, `PcaListContainer.tsx`) — consistent, no lagging places found.

## Review

The review was run by 5 parallel agents (CLAUDE.md compliance, quick bug scan, history/git blame, search for feedback on past PRs in the same area, compliance with existing code comments) on the current diff (`main...pr-1177-head`), after which each finding received an independent confidence score on a 0–100 scale (publication threshold — 80).

**Passed the threshold ≥80:**

- **[100/100] The `CREATING` state badge on the CA details page lost its translation — the only untranslated string among all status badges.** `PcaDetailsView.tsx:49`: it was `<Badge icon="bolt" variant="info" text={t\`Creating\`} />`, now it is `<Spinner size="18" /> Creating` — a literal English string directly in JSX, without `t`/`<Trans>`. The neighboring states in the same object (`AWAITING_CERTIFICATE`, `READY`, `FAILED`) still use `t`. Confirmed by the `messages.po` diff: the string `"Creating"` does not appear as a new `msgid` — meaning `lingui extract` (`pnpm check-i18n`) did not see it and never will; it will stay English in any locale, including German. The counterpart in `PcaTableRow.tsx:36` (`text: t\`Creating\`,`) is correct — the regression is only in `PcaDetailsView`. Nothing in CI catches it (the Lingui macro is a string compilation step, not a type).

**Did not pass the threshold (observations, not findings):**

- **[78, rejected] The certificate import file upload now accepts only `.json`, whereas previously it accepted `.pem`/`.crt`/`.cer` directly with a fallback to raw text.** The same question as in the previous version of the report (was 50/100) — the new scoring agent raised it to 78 after checking the history: `accept=".pem,.crt,.cer,.json"` was added deliberately in a separate PR (`fc861d5`, #901) precisely to support direct certificate upload, not just JSON. It did not pass the threshold: the change is intentional and covered by a test (renamed to "ignores non-JSON file uploads"), manual pasting into the text field is untouched — this is a real but deliberate and mitigated UX narrowing, not a defect.
- **[75, rejected] Removal of `"UNEXPECTED"` from `CertificateAuthorityStateSchema` — the same finding as in the 2026-08-14 version, with a stronger evidence base.** The new agents confirmed: the state has been in the schema since the very first commit of the file (`034d591`, #761) — i.e. it was part of the original design rather than added later as protection against a specific incident; the architecture document `packages/aurora/docs/0011_clavis.md` (not touched by this PR) still lists `UNEXPECTED` among the "Relevant PCA states". If the backend can still send this state, `pcaRouter.list`/`getById`/`import` will fail entirely via `parseOrThrow`. The threshold was not met for the same reason as before: there is no way to independently verify whether the backend/Clavis team has confirmed that this state is no longer possible — if so, the finding is dropped entirely.
- **[75, rejected] The tooltip `title="Download PEM file"` on the new download button is not translated.** `DetailsInfo.tsx:47`, `codeBlockFooter={<Icon icon="download" title="Download PEM file" .../>}` — the only `Icon` with a `title` in the whole repository, and the only untranslated one; the file does not import `useLingui`. Not raised to 80: this string (unlike the `CREATING` badge) was added back in the very first commit of the PR (`d8a2186`, 2026-08-13) and was already checked by the previous version of this report without a finding — in practice it is a native HTML `title` tooltip rather than visible UI text, which is milder in impact.
- **[75, rejected] `isValidPem` became dead code** after `288977d` switched its only consumer to `isValidCsr`. Confirmed with `git grep` — not a single import in the repository. Not caught by lint/typecheck (the unused-export rule is not enabled), but not critical either — just an unused export.
- **[30, rejected] The comment `"", // ... "Delete CA" button` in `PcaCertificatesListContainer.tsx:82` does not match the actual row menu (`PcaCertificatesTableRow.tsx`, which has only "Show Details", no delete).** The comment existed on `main` before this PR (copied from the neighboring `PcaListContainer.tsx`, where the menu does contain "Delete CA") — this PR neither introduced nor copy-pasted it, it just didn't fix it. A purely documentation inaccuracy with no functional effect.

Everything else was checked and not raised as a finding: the `"Subject"` → `"Subject Information"` rename is consistent everywhere and correctly made it into `messages.po`; the switch to juno `Spinner`/`Icon` in `PcaTableRow.tsx` did not lose the `t` wrapper (only `PcaDetailsView.tsx` was affected); the `getById` invalidations in `IssueSelfSignedCertificateModal`/`ImportExternallySignedCertificateModal` are correct and targeted; the test `ParsedCertificateInfo.test.tsx` still mocks `parseCsrInfo` as an async function (`mockResolvedValue`/`mockRejectedValue`) — not a bug: the mock replaces the module entirely, the real synchronous implementation is not called, and the comment "Invalid/malformed CSR should quietly render no parsed info" in `ParsedCertificateInfo.tsx` continues to hold (verified against the current `QueryClient` config — a parse error quietly yields `data: undefined` → `fields: []` → the component renders `null`).

---
Analyzed: 2026-08-19 · commit `de468bd6`
