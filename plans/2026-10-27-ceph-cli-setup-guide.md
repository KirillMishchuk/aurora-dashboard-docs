---
type: plan
date: 2026-10-27
status: not-implemented
issue: [1208]
---
# Plan: Ceph CLI setup guide modal

**Date:** 2026-10-27 · **Status:** not implemented
**Base:** `c3-test` @ `af14a6a0` · 2 commits behind origin/main
**Reviewed:** 2 findings, 2 fixed

## Overview

Add a Keppel-style "how to use this from your command line" guide for Ceph S3 object storage (issue #1208). A new info-only `CliSetupModal` shows numbered steps with copyable command blocks for AWS CLI, s3cmd and rclone. A Juno `Select` picks the tool. The endpoint and region are filled in from the existing `storage.ceph.containers.status` query, and credentials stay placeholders. The modal opens from the bucket list's More Actions menu (generic commands) and from the in-bucket header's actions menu (commands pre-filled with that bucket's name). Each opening place also lets the user jump to Manage Credentials. The change is client-only: no new BFF procedure and no secret handling.

## Decisions

- **D1. Where the guide lives:** A standalone `CliSetupModal`, opened from a "CLI Setup" item in the bucket list's More Actions menu, with a button that opens Manage Credentials. `ManageCredentialsModal` stays as it is (an AWS CLI snippet was removed from it on 29.09 as unnecessary).
- **D2. Tools covered:** AWS CLI, s3cmd and rclone, switched with a Juno `Select`. The SAP guide linked in the issue (`documentation.global.cloud.sap/.../ceph-cli/`) could not be read (DNS failure from the planning environment), so the snippets below are built from the upstream tool docs and the BFF's own S3 client settings. Matching them against the SAP guide is an open question and a live check.
- **D3. Credentials in the commands:** Placeholders only. The endpoint and region come from `containers.status`. The access key ID and secret are entered at the tool's interactive prompt (AWS CLI) or shown as `<ACCESS_KEY_ID>` / `<SECRET_ACCESS_KEY>` (s3cmd, rclone config files), with a pointer to Manage Credentials. No secret is fetched or held.
- **D4. Entry points:** Both the bucket list (generic, `<bucket-name>` placeholder) and the in-bucket header's actions menu (`BucketHeaderActions`), through an optional `bucketName` prop on the same modal.

## Architecture Analysis

**Current state:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx` (`CephBuckets`): the bucket list. Zone 1 has a More Actions `PopupMenu` (lines 315-329) whose only item is "Manage Credentials" (`data-testid="manage-credentials-action"`), deliberately not permission-gated because opening it is a read. `ManageCredentialsModal` is mounted once in the single unconditional `return` (line 447-452), so it survives the page switching into the `NO_CEPH_CREDENTIALS` branch. The More Actions menu only renders in the success branch.
- `.../Ceph/Credentials/ManageCredentialsModal.tsx`: already reads `trpcReact.storage.ceph.containers.status.useQuery({ project_id }, { enabled: isOpen && !!projectId, retry: false, staleTime: Infinity })` (lines 93-96) and renders endpoint/region with `ClipboardText`, plus an error `Status` titled "Connection Details Unavailable". The new modal uses exactly the same query input and options, so both share one cache entry.
- `packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts:36`: `status` is a `cephProcedure` (works without credentials) that returns `{ hasCredentials, endpoint: ctx.cephEndpoint, region: ctx.cephRegion }`. `endpoint` is the catalog's Ceph endpoint with any `/swift/...` suffix stripped (`packages/aurora/src/server/Storage/cephProcedure.ts:39-40`). `region` is the S3 signing region (`CEPH_REGION`).
- `packages/aurora/src/server/Storage/clients/s3Client.ts:6,31`: the BFF uses `forcePathStyle: true` ("Ceph does not support virtual-hosted-style URLs"). The CLI instructions have to force path-style addressing too.
- `.../Ceph/Buckets/BucketHeader.tsx`: in-bucket `ContentHeader`. Owns `activeModal: ModalType | null`, renders `BucketHeaderActions` (the actions menu) and `BucketModals` (all bucket modals keyed by `ModalType`). It is rendered unconditionally on the Ceph objects page (`.../storage/$provider/$storageType/$containerName/objects/index.tsx:197`).
- `.../Ceph/Buckets/BucketHeaderActions.tsx`: every item is a gated mutation, and the component returns `null` when none is permitted (lines 52-62). Its docblock says so. `BucketHeaderActions.test.tsx:54` asserts "renders nothing when all six permissions are false".
- `.../Ceph/Buckets/BucketModals.tsx`: `ModalType` union (lines 28-35), and one `isOpen={activeModal === "..."}` block per modal.
- Juno `@cloudoperators/juno-ui-components` is pinned at `9.7.1`. `CodeBlock` (`content | children`, `heading`, `wrap`, `size`, `copy = true`) copies the rendered `textContent` of its code element (checked in `build/index.js`), so blocks must hold only copy-ready text, with no `$ ` prompt prefix and no sample output. `Select` / `SelectOption` usage pattern: `.../network/securitygroups/$securityGroupId/-modals/AddRuleModal/sections/RuleTypeSection.tsx:20` (`<Select id label value onChange={(value) => ...}>`). No client code uses `CodeBlock` yet.
- `packages/aurora/src/client/hooks/useModalTracking.ts`: `{ isOpen, actionPrefix }` → `{ trackClose, markSubmitted, resetTracking }`, used by every modal (Manage Credentials uses `storage.ceph.credentials.manage`).
- Tests: vitest + jsdom, colocated. `ManageCredentialsModal.test.tsx` shows how to mock `@/client/trpcClient`, `@tanstack/react-router` (for `useModalTracking`), `useProjectId` and Juno. `Buckets/index.test.tsx` mocks `../Credentials/ManageCredentialsModal` with a stub (lines 102-110).
- i18n: Lingui, catalogs in `packages/aurora/src/locales/{en,de}/messages.{po,ts}` (tracked). `check-i18n` runs `lingui extract --clean && lingui compile`.

**Proposed changes:**

- New folder `.../Ceph/CliSetup/` containing:
  - `cliSetupSnippets.ts`: pure functions that build the per-tool command text from `{ endpoint, region, bucketName? }`. No React, no i18n, fully unit-testable.
  - `CliSetupModal.tsx`: info-only modal (no confirm button) with an intro sentence, a "Manage Credentials" button, the tool `Select`, and an ordered list of steps (a translated label plus one `CodeBlock` each).
- Bucket list: add a "CLI Setup" item to More Actions and mount `CliSetupModal` next to `ManageCredentialsModal` in the unconditional return. Its "Manage Credentials" button closes the CLI modal and opens the credentials modal (never two stacked modals, per copilot-instructions B.5).
- Bucket page: add `"cliSetup"` and `"manageCredentials"` to `ModalType`. `BucketModals` renders `CliSetupModal` (with `bucketName`) and a `ManageCredentialsModal`, and gets an optional `onOpenModal` prop so the CLI modal can switch to the credentials modal. `BucketHeaderActions` always shows "CLI Setup", so the menu no longer disappears for read-only users.
- Why this fits: it reuses the More Actions → modal pattern, the existing `status` query and cache entry, the existing `ModalType` machinery on the bucket page, and Juno components only. Nothing touches the BFF or the secret-handling code.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| The snippets don't match what the SAP guide or the real RGW expects (path-style, region name, `provider = Ceph` for rclone, s3cmd `host_bucket`). Wrong commands are worse than none. | High | The snippets follow the BFF's own client settings (`forcePathStyle: true`, `status.endpoint` / `status.region`) and upstream docs: AWS CLI `--endpoint-url` ([AWS CLI endpoints](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-endpoints.html)) and `s3.addressing_style path` ([AWS CLI S3 config](https://docs.aws.amazon.com/cli/latest/topic/s3-config.html)), plus rclone's Ceph provider, where `force_path_style` defaults to `true` ([rclone S3](https://rclone.org/s3/)). All snippet text lives in `cliSetupSnippets.ts`, so a correction touches one file. Listed under Live-environment checks and Open Questions. |
| `BucketHeaderActions` no longer returns `null` when the user has no mutation permissions. A read-only user now sees a menu with one item. | Medium | Intended: "CLI Setup" is a read, like "Manage Credentials" on the list. Update the docblock and replace the "renders nothing" test with "renders only CLI Setup". `[BREAKING]` tag on that step. |
| A second `ManageCredentialsModal` instance on the bucket page. Deleting the last key there makes the bucket page's own queries fail with `NO_CEPH_CREDENTIALS`. | Medium | `BucketHeader` (and so `BucketModals`) is rendered unconditionally on the Ceph objects page (`objects/index.tsx:197`), so the modal is not unmounted mid-operation. Check by hand on the mock (Testing Plan). |
| `CodeBlock` copies `textContent`, so a `$ ` prefix or sample prompt output would end up in the user's clipboard. | Medium | Code blocks hold only runnable text or config-file content. Interactive prompts are described in the step label, not shown in the block. A unit test asserts that no snippet line starts with `$`. |
| Endpoint URLs with a path (e.g. a mock or proxy prefix) can't be expressed in s3cmd's `host_base` (host only). | Low | `endpointParts()` returns `host` and `useHttps` for s3cmd. AWS CLI and rclone get the full endpoint. Note in the code that s3cmd drops any path, and check the real endpoint shape live. |
| `status` fails (catalog has no Ceph endpoint, or the region isn't configured). | Low | Show the same error `Status` as Manage Credentials ("Connection Details Unavailable"). The tool `Select` stays visible above it, but the body shows only that `Status`: no step labels and no code blocks, so no command with an empty endpoint is ever rendered (Step 2.5; covered by a unit test). |
| Bucket names in commands could, in principle, carry shell metacharacters. | Low | Bucket names reaching the page are S3-valid (lowercase letters, digits, `.`, `-`), and React escapes the text. No quoting is needed. `bucketName` is only text interpolation. |
| Modal naming: copilot-instructions name modals `<Verb><Resource>Modal`. | Low | `CliSetupModal` is the name the user chose (D1). Keep it. |

## Prerequisites

- [ ] None in the repo. The local mock already serves `containers.status` (Ceph catalog endpoint + `MOCK_CEPH_REGION`) and accepts any EC2 key, so no mock extension is needed.

## Implementation Steps

### Step 1: Create the snippet builders

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/CliSetup/cliSetupSnippets.ts` - new, pure module

**What to do:**

1. Export constants:
   - `CLI_TOOLS = ["awscli", "s3cmd", "rclone"] as const`, `export type CliTool = (typeof CLI_TOOLS)[number]`
   - `CLI_TOOL_LABELS: Record<CliTool, string> = { awscli: "AWS CLI", s3cmd: "s3cmd", rclone: "rclone" }` (product names, not translated)
   - `CLI_PROFILE_NAME = "ceph"` (AWS CLI profile and rclone remote name)
   - `ACCESS_KEY_PLACEHOLDER = "<ACCESS_KEY_ID>"`, `SECRET_KEY_PLACEHOLDER = "<SECRET_ACCESS_KEY>"`, `BUCKET_PLACEHOLDER = "<bucket-name>"`, `LOCAL_FILE_PLACEHOLDER = "<local-file>"`, `OBJECT_KEY_PLACEHOLDER = "<object-key>"`
2. Export `type CliSetupStepId = "configure" | "configureEndpoint" | "list" | "upload" | "download"` and `interface CliSetupStep { id: CliSetupStepId; code: string }`. Labels are not stored here; the component maps `id` (plus tool and whether a bucket is given) to a translated label.
3. Export `endpointParts(endpoint: string): { host: string; useHttps: boolean }`. Try `new URL(endpoint)` → `{ host: url.host, useHttps: url.protocol === "https:" }`. On a parse error, fall back to `{ host: endpoint.replace(/^[a-z]+:\/\//i, "").replace(/\/.*$/, ""), useHttps: !endpoint.startsWith("http://") }`. Add a comment that s3cmd's `host_base` cannot hold a path, so any path in the endpoint is dropped for s3cmd only.
4. Export `buildCliSetupSteps(tool: CliTool, opts: { endpoint: string; region: string; bucketName?: string }): CliSetupStep[]`. Let `bucket = opts.bucketName ?? BUCKET_PLACEHOLDER` and `ep = opts.endpoint`. Join multi-line code with `"\n"`. No `$ ` prefixes anywhere.
   - `awscli`:
     - `configure`: `aws configure --profile ceph`
     - `configureEndpoint`: two lines, `aws configure set region ${region} --profile ceph` and `aws configure set s3.addressing_style path --profile ceph`
     - `list`: with `bucketName`, `aws s3 ls s3://${bucket}/ --profile ceph --endpoint-url ${ep}`; without it, `aws s3 ls --profile ceph --endpoint-url ${ep}` (lists buckets)
     - `upload`: `aws s3 cp <local-file> s3://${bucket}/ --profile ceph --endpoint-url ${ep}`
     - `download`: `aws s3 cp s3://${bucket}/<object-key> . --profile ceph --endpoint-url ${ep}`
     - `--endpoint-url` per command rather than `endpoint_url` in the profile: the flag works on every AWS CLI version, while profile `endpoint_url` needs a recent CLI.
   - `s3cmd`, using `const { host, useHttps } = endpointParts(ep)`:
     - `configure`: a `~/.s3cfg` body with these lines: `[default]`, `access_key = <ACCESS_KEY_ID>`, `secret_key = <SECRET_ACCESS_KEY>`, `host_base = ${host}`, `host_bucket = ${host}`, `bucket_location = ${region}`, `use_https = ${useHttps ? "True" : "False"}`. `host_bucket` without `%(bucket)s` means path-style.
     - `list`: `s3cmd ls s3://${bucket}` with `bucketName`, otherwise `s3cmd ls`
     - `upload`: `s3cmd put <local-file> s3://${bucket}/`
     - `download`: `s3cmd get s3://${bucket}/<object-key>`
   - `rclone`:
     - `configure`: a config section with these lines: `[ceph]`, `type = s3`, `provider = Ceph`, `access_key_id = <ACCESS_KEY_ID>`, `secret_access_key = <SECRET_ACCESS_KEY>`, `endpoint = ${ep}`, `region = ${region}`. Comment: `force_path_style` defaults to `true`, so it is not set.
     - `list`: `rclone ls ceph:${bucket}` with `bucketName`, otherwise `rclone lsd ceph:`
     - `upload`: `rclone copy <local-file> ceph:${bucket}/`
     - `download`: `rclone copy ceph:${bucket}/<object-key> .`
5. Add a short module docblock: credentials are always placeholders (decision D3) and the secret never enters this module. Path-style mirrors `server/Storage/clients/s3Client.ts`. Blocks must stay copy-ready because Juno `CodeBlock` copies their `textContent`.

**Expected outcome:**

- A deterministic, React-free builder for all three tools, with and without a bucket name.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck` passes. The unit tests from Step 5 pass.

---

### Step 2: Create `CliSetupModal` [CAREFUL]

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/CliSetup/CliSetupModal.tsx` - new

**What to do:**

1. Props: `interface CliSetupModalProps { isOpen: boolean; onClose: () => void; bucketName?: string; onManageCredentials?: () => void }`. Export `const CliSetupModal`.
2. Hooks: `useLingui()`, `useProjectId()`, and `useModalTracking({ isOpen, actionPrefix: "storage.ceph.cliSetup" })`. Use local state `const [tool, setTool] = useState<CliTool>("awscli")`, reset to `"awscli"` in a `useEffect` when `isOpen` becomes `false`.
3. Status query, identical in input and options to `ManageCredentialsModal.tsx:93-96` so both share one cache entry: `trpcReact.storage.ceph.containers.status.useQuery({ project_id: projectId ?? "" }, { enabled: isOpen && !!projectId, retry: false, staleTime: Infinity })`. Read `data`, `error` and `isLoading`.
4. `handleClose`: `trackClose(); resetTracking(); onClose()`. `handleManageCredentials`: `trackClose(); resetTracking(); onManageCredentials?.()`. The parent swaps modals; this component never opens the credentials modal itself.
5. Render a Juno `Modal` with `title={bucketName ? t\`Use Bucket "${bucketName}" from the Command Line\` : t\`Use S3 Object Storage from the Command Line\`}`, `open={isOpen}`, `size="large"`, `onCancel={handleClose}`, `cancelButtonLabel={t\`Close\`}`, and no `onConfirm` (info-only). Inside, a `<Stack direction="vertical" gap="4">` with:
   - A `<p>` intro (plain body text, like `ManageCredentialsModal`'s section description): `<Trans>Configure a command-line tool to work with this project's S3 object storage. You need an access key ID and a secret access key, which you can find or create in Manage Credentials.</Trans>`
   - When `onManageCredentials` is set: `<Stack direction="horizontal" className="justify-end"><Button label={t\`Manage Credentials\`} onClick={handleManageCredentials} data-testid="cli-setup-manage-credentials" /></Stack>` (default variant: the modal has no primary action).
   - `<Select id="cli-setup-tool" label={t\`Tool\`} value={tool} onChange={(value) => { const v = String(value ?? ""); if ((CLI_TOOLS as readonly string[]).includes(v)) setTool(v as CliTool) }} data-testid="cli-setup-tool">` with one `<SelectOption value={id} label={CLI_TOOL_LABELS[id]} />` per `CLI_TOOLS` entry. Follow `RuleTypeSection.tsx:20` for the prop shape.
   - Body states:
     - `isLoading`: `<Status status="progress" title={t\`Loading Connection Details...\`} />`
     - `error`: `<Status status="error" title={t\`Connection Details Unavailable\`} body={error.message} />` (same title as Manage Credentials, which reuses the catalog string)
     - `data`: `const steps = buildCliSetupSteps(tool, { endpoint: data.endpoint, region: data.region, bucketName })`, rendered as `<ol className="list-decimal space-y-4 pl-6">`. Each step is `<li key={step.id}>` holding `<p className="mb-2">{stepLabel(step.id)}</p>` and `<CodeBlock wrap={false} data-testid={\`cli-setup-step-${step.id}\`}>{step.code}</CodeBlock>`.
6. `stepLabel(id)`: a local function returning translated strings, depending on `tool` and `bucketName`:
   - `configure`:
     - awscli: t`Create a profile. Enter your access key ID and secret access key when prompted, and leave the other prompts empty:`
     - s3cmd: t`Save this as ~/.s3cfg and replace the placeholders with your access key ID and secret access key:`
     - rclone: t`Add this to your rclone configuration file (run "rclone config file" to find it) and replace the placeholders with your access key ID and secret access key:`
   - `configureEndpoint` (awscli only): t`Set the region and path-style addressing for this profile:`
   - `list`: t`List the objects in this bucket:` when `bucketName` is set, otherwise t`List your buckets:`
   - `upload`: t`Upload a file:`
   - `download`: t`Download an object:`
7. After the list, add a closing `<p>` only when `bucketName` is not set: `<Trans>Replace {BUCKET_PLACEHOLDER} with the name of one of your buckets.</Trans>`. Lingui needs a variable here: `const placeholder = BUCKET_PLACEHOLDER`, then `<Trans>Replace {placeholder} with ...</Trans>`.
8. Imports in the repo's order (React, Lingui, trpc, Juno, then local), matching `ManageCredentialsModal.tsx`. Juno imports: `Modal, Stack, Button, Select, SelectOption, CodeBlock, Status`.
9. Add a docblock covering: info-only; no secret ever handled (D3), so no credential list or reveal calls are made; shares the `containers.status` cache entry with `ManageCredentialsModal` on purpose; `onManageCredentials` is a callback so the parent can swap modals instead of stacking them.

**Expected outcome:**

- The modal renders steps for the selected tool with the live endpoint and region, and switching the `Select` swaps the steps.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck` and `lint` pass. Tests from Step 5 pass.

---

### Step 3: Wire the modal into the bucket list

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx` - menu item and mount

**What to do:**

1. Import `CliSetupModal` from `../CliSetup/CliSetupModal`. Add `const [cliSetupModalOpen, setCliSetupModalOpen] = useState(false)` next to `credentialsModalOpen` (line 63).
2. In the More Actions `PopupMenuOptions` (lines 319-328), add after "Manage Credentials": `<PopupMenuItem label={t\`CLI Setup\`} onClick={() => setCliSetupModalOpen(true)} data-testid="cli-setup-action" />`. Extend the existing comment: also not permission-gated, because it is a read.
3. In the final unconditional `return` (lines 447-452), mount next to `ManageCredentialsModal`: `<CliSetupModal isOpen={cliSetupModalOpen} onClose={() => setCliSetupModalOpen(false)} onManageCredentials={() => { setCliSetupModalOpen(false); setCredentialsModalOpen(true) }} />`.

**Expected outcome:**

- More Actions → CLI Setup opens the guide with `<bucket-name>` placeholders. Its Manage Credentials button replaces it with the credentials modal.

**Verification:**

- The `Buckets/index.test.tsx` additions from Step 5 pass. Existing tests in that file still pass.

---

### Step 4: Wire the modal into the bucket page header [BREAKING]

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketModals.tsx` - new modal types and mounts
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx` - always-visible CLI Setup item
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeader.tsx` - pass `onOpenModal` to `BucketModals`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Credentials/ManageCredentialsModal.tsx` - docblock only (mount points)

**What to do:**

1. `BucketModals.tsx`:
   - Extend `ModalType` with `| "cliSetup" | "manageCredentials"`.
   - Add an optional prop `onOpenModal?: (modal: ModalType) => void` to `BucketModalsProps`.
   - Import `CliSetupModal` from `../CliSetup/CliSetupModal` and `ManageCredentialsModal` from `../Credentials/ManageCredentialsModal`. After the existing modal blocks, render:
     - `<CliSetupModal isOpen={activeModal === "cliSetup"} onClose={onClose} bucketName={bucketName} onManageCredentials={onOpenModal ? () => onOpenModal("manageCredentials") : undefined} />`
     - `<ManageCredentialsModal isOpen={activeModal === "manageCredentials"} onClose={onClose} />`
   - Update the docblock's modal list.
2. `BucketHeaderActions.tsx`:
   - Remove the `hasAnyAction` calculation and the `return null` (lines 52-62).
   - No new prop: reuse the existing `onOpenModal` and add `<PopupMenuItem label={t\`CLI Setup\`} onClick={() => onOpenModal("cliSetup")} data-testid="bucket-cli-setup-action" />` as the first item, always rendered.
   - Rewrite the docblock: the menu always renders because "CLI Setup" is an ungated read (like "Manage Credentials" on the bucket list); every other item is a gated mutation.
3. `BucketHeader.tsx`: pass `onOpenModal={openModal}` to `<BucketModals ...>`. `openModal` replaces `activeModal`, so switching from CLI Setup to Manage Credentials closes one modal and opens the other, never both.
4. `ManageCredentialsModal.tsx`: rewrite the docblock paragraph at lines 65-67 ("Mounted once, outside every early `return` in `CephBuckets` ...") so it names both mount points. (a) `CephBuckets` (`Buckets/index.tsx`), outside every early `return`, because deleting the last credential flips that page into the `NO_CEPH_CREDENTIALS` branch and the modal must survive that. (b) `BucketModals` on the bucket page, which is safe for the same transition because `BucketHeader` is rendered unconditionally on the Ceph objects page (`routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.tsx:197`), so the modal stays mounted when the page's queries start failing with `NO_CEPH_CREDENTIALS`. No code change in that file.

**Expected outcome:**

- On a bucket page, the actions kebab is always visible. "CLI Setup" opens the guide with that bucket's name filled in, and "Manage Credentials" in it switches to the credentials modal.

**Verification:**

- The updated `BucketHeaderActions.test.tsx` passes (Step 5). Manual check on the mock (Testing Plan, items 3-4).

---

### Step 5: Add and update tests

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/CliSetup/cliSetupSnippets.test.ts` - new
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/CliSetup/CliSetupModal.test.tsx` - new
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.test.tsx` - extend
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.test.tsx` - update

**What to do:**

1. `cliSetupSnippets.test.ts`: the cases listed under Unit tests below.
2. `CliSetupModal.test.tsx`: copy the mocking setup from `Credentials/ManageCredentialsModal.test.tsx`: `@/client/trpcClient` with a controllable `containers.status.useQuery`, `@tanstack/react-router` for `useRouteContext` used by `useModalTracking`, and `@/client/hooks/useProjectId`. Use the I18n wrapper the same way that file does. Cases are listed under Unit tests.
3. `Buckets/index.test.tsx`: add `vi.mock("../CliSetup/CliSetupModal", ...)` with a stub that renders `data-testid="cli-setup-modal"` when open and a button that calls `onManageCredentials`, in the same style as the `ManageCredentialsModal` stub (lines 102-110). Add tests in the "Credentials" describe block (or a new "CLI Setup" block).
4. `BucketHeaderActions.test.tsx`: replace "renders nothing when all six permissions are false" (line 54) with "renders only CLI Setup when all six permissions are false". Extend "shows every permitted item" to include "CLI Setup". Add "clicking CLI Setup calls onOpenModal('cliSetup')".

**Expected outcome:**

- New behaviour is covered, and the old "menu hidden" expectation is replaced.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test` passes.

---

### Step 6: Update i18n catalogs and add a changeset

**Files to modify/create:**

- `packages/aurora/src/locales/en/messages.po`, `packages/aurora/src/locales/de/messages.po`, `packages/aurora/src/locales/en/messages.ts`, `packages/aurora/src/locales/de/messages.ts` - regenerated
- `.changeset/ceph-cli-setup-guide.md` - new

**What to do:**

1. Run `pnpm --filter @cobaltcore-dev/aurora check-i18n` and keep the regenerated catalogs. German `msgstr` stay empty, as in earlier PRs.
2. Create the changeset:
   ```
   ---
   "@cobaltcore-dev/aurora": minor
   ---

   - Ceph object storage: add a "CLI Setup" guide (AWS CLI, s3cmd, rclone) with the project's S3 endpoint and region, opened from the bucket list's More Actions menu and from a bucket's actions menu (pre-filled with the bucket name)
   - The bucket actions menu is now always shown, since "CLI Setup" needs no permissions
   ```

**Expected outcome:**

- Catalogs contain the new strings. A minor bump is queued.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora check-i18n` exits 0, and `pnpm format:check` passes.

## Testing Plan

**Unit tests** (vitest, colocated `*.test.ts(x)`):

- [ ] `buildCliSetupSteps("awscli", { endpoint: "https://s3.example.com", region: "eu-de-1" })` returns ids `configure, configureEndpoint, list, upload, download`. `list` is `aws s3 ls --profile ceph --endpoint-url https://s3.example.com`. `configureEndpoint` contains `region eu-de-1` and `s3.addressing_style path`.
- [ ] With `bucketName: "my-bucket"`, every awscli, s3cmd and rclone step that references a bucket uses `my-bucket`, and none contains `<bucket-name>`. Without it, `upload`/`download` contain `<bucket-name>`.
- [ ] s3cmd `configure` for `https://s3.example.com:8443/prefix` has `host_base = s3.example.com:8443`, `host_bucket = s3.example.com:8443` and `use_https = True`. For `http://localhost:8090` it has `use_https = False`.
- [ ] rclone `configure` contains `provider = Ceph`, `endpoint = <full endpoint>` and `region = <region>`.
- [ ] For all tools: no line of any `code` starts with `$`, and every snippet that contains a credential uses `<ACCESS_KEY_ID>` / `<SECRET_ACCESS_KEY>` (no other credential-looking value).
- [ ] `endpointParts` falls back without throwing on a non-URL string.
- [ ] `CliSetupModal`: with status data, renders the AWS CLI steps by default, and the endpoint appears in the `list` code block.
- [ ] `CliSetupModal`: choosing "rclone" in the `Select` shows `provider = Ceph` and no longer shows `aws configure`.
- [ ] `CliSetupModal`: with `bucketName="my-bucket"`, the title names the bucket and the list label is "List the objects in this bucket:".
- [ ] `CliSetupModal`: a status error renders "Connection Details Unavailable", keeps the tool `Select`, and renders no step labels (e.g. no "List your buckets:") and no `cli-setup-step-*` blocks. Loading renders the progress `Status`.
- [ ] `CliSetupModal`: the Manage Credentials button calls `onManageCredentials` and is absent when the prop is not set. Close calls `onClose`.
- [ ] `CliSetupModal`: the status query is called with `{ project_id }` only (no extra keys), keeping the shared cache entry.
- [ ] `Buckets/index.test.tsx`: More Actions → `cli-setup-action` opens the stub. The stub's Manage Credentials button closes it and opens `manage-credentials-modal`.
- [ ] `BucketHeaderActions.test.tsx`: the menu renders with only "CLI Setup" when all permissions are false, and clicking it calls `onOpenModal("cliSetup")`.

**Manual check on the local mock** (`../local-mock-backend/`, `./run-all.sh`):

1. Log in, open a project's Ceph buckets (`/projects/<id>/storage/ceph/containers`), and create an access key via "Setup Required" → Manage Credentials if prompted (the mock starts with no EC2 keys).
2. More Actions → "CLI Setup". Check that the endpoint shown matches Manage Credentials → Connection Details, the region is `us-east-1` (default `MOCK_CEPH_REGION`), and switching AWS CLI / s3cmd / rclone swaps the steps. Copy one block and paste it into a text editor: no `$`, no extra text.
3. Click "Manage Credentials" in the guide. Check that the guide closes and the credentials modal opens, with no two modals stacked.
4. Open one of the five seeded buckets. The header kebab shows "CLI Setup" first, and the guide's commands contain that bucket's name. From there, open Manage Credentials, delete the last key, and check that the modal stays open and usable (the page underneath may switch to an error state).
5. Optional: with AWS CLI installed, run the generated `list` command against the mock endpoint using any access key or secret (the mock doesn't check signatures). It should list buckets. s3cmd may not work if the mock endpoint has a path prefix (s3cmd drops paths, see Risks). That's expected on the mock.

**Live-environment checks**

- [ ] Against a real SAP Ceph RGW region with a real EC2 key, run each tool's configure, list, upload and download commands exactly as rendered. All succeed if the path-style and region choices are right. A `PermanentRedirect`, `AuthorizationHeaderMalformed` or signature error means the region or addressing in the snippets is wrong.
- [ ] Compare the snippets with the SAP guide `documentation.global.cloud.sap/docs/customer/storage/obj-v2-ceph/ceph-cli/` (unreachable during planning). Any tool, flag or value it prescribes differently goes into `cliSetupSnippets.ts`.
- [ ] Confirm the real `status.endpoint` has no path component. If it has one, the s3cmd `host_base` needs rethinking.

## Acceptance Criteria

- [ ] The bucket list's More Actions menu has "CLI Setup", which opens a modal with numbered steps and copyable code blocks for AWS CLI, s3cmd and rclone, chosen with a `Select`.
- [ ] The endpoint and region in the commands come from `storage.ceph.containers.status`. Credentials appear only as the interactive prompt or the `<ACCESS_KEY_ID>` / `<SECRET_ACCESS_KEY>` placeholders, and no credential or reveal call is made by the guide.
- [ ] On a bucket page, the actions menu always shows "CLI Setup", and the commands use that bucket's name.
- [ ] From the guide, "Manage Credentials" replaces it with the credentials modal on both pages, never stacking modals.
- [ ] Copying a block puts only runnable or config text on the clipboard.
- [ ] A failed `status` shows "Connection Details Unavailable" instead of commands with an empty endpoint.
- [ ] No regressions in Manage Credentials, the bucket list or the bucket header modals.
- [ ] `pnpm --filter @cobaltcore-dev/aurora test`, `typecheck`, `lint` and `check-i18n`, plus `pnpm format:check`, pass. A `.changeset/ceph-cli-setup-guide.md` minor changeset exists.

## Open Questions

- The SAP guide could not be read (DNS failure from the planning environment). The implementer or reviewer should compare the snippets with it if reachable, especially the recommended tools, the profile or remote naming, and whether it uses `--endpoint-url` per command or a profile `endpoint_url`.
- `aws configure set s3.addressing_style path --profile ceph` follows the documented `aws configure set default.s3.addressing_style path` form adapted to `--profile`. Confirm it writes `s3 =\n  addressing_style = path` under `[profile ceph]` in `~/.aws/config`. If not, use `aws configure set profile.ceph.s3.addressing_style path`.
- The guide is not reachable from the `NO_CEPH_CREDENTIALS` "Setup Required" screen, because More Actions renders only in the success branch. That's fine for now, since that screen's only action is Manage Credentials. Revisit if users ask.
