# [Feature](storage): manage S3 access keys for Ceph object storage

**Description**

Ceph object storage is used through S3 access keys (Keystone EC2 credentials), but the dashboard
has no screen for them. A user can see their buckets and objects, and cannot see, recover, rotate
or remove the key those buckets are reached with.

Add a **Manage Credentials** modal on the Ceph bucket list that lists the access keys the user
holds in the project, reveals a key's secret on request, creates and deletes keys, and shows the
S3 endpoint and region next to them.

**Problem Statement**

Reported on `/projects/<id>/storage/ceph/containers`, in a project that already had a working key:

> I have no option to see or manage my credentials.

Aurora creates an S3 access key on the user's behalf, goes on using it on their behalf, and never
hands it over. Three gaps follow from that:

1. **The secret never reaches the user.** The "S3 Object Storage: Setup Required" screen creates a
   key and drops the secret on the floor: `create` answers with `{ access, secret }`,
   `CredentialPrompt` ignores the response, invalidates the bucket list and reloads the page
   (`Ceph/Buckets/CredentialPrompt.tsx:17-26`, `Ceph/Buckets/index.tsx:235`). The key works
   afterwards, but only inside Aurora — the BFF reads it out of Keystone itself to sign every Ceph
   request (`Storage/middleware/resolveEC2Credential.ts`). Anyone who wants to reach the same
   buckets with `aws s3`, s3cmd, rclone or a backup job has nothing to configure them with.
2. **Nothing lists, adds or removes a key afterwards.** `CredentialPrompt` renders on exactly one
   condition — the bucket listing failing because this user holds no key in this project
   (`Ceph/Buckets/index.tsx:234`). That stops being true the moment they have one, and no other
   screen in the dashboard mentions credentials. There is no way to see which key is in use, no
   way to add a second one alongside it, and no delete at all — a key that leaks, or one left
   behind by someone who has moved on, cannot be revoked from the UI.
3. **The endpoint and region are nowhere in the UI.** Both are known only to the server
   (`Storage/cephProcedure.ts:22`, `resolveS3Config`). Even holding a valid key, nothing on screen
   says which host and region to point a client at.

The secret is recoverable: Keystone EC2 credentials are not Application Credentials — the blob is
stored encrypted and decrypted on every read, and the owner may read their own under the default
policy. Aurora's own BFF already performs that read on every single Ceph request in order to sign
the S3 call, so showing it to its owner exposes nothing that was not already crossing the BFF.

**Proposed Solution**

A **Manage Credentials** modal, reachable from the overflow ("More Actions") menu next to
"Create Bucket", from the rewritten "S3 Object Storage: Setup Required" screen, and from the
"S3 Credentials No Longer Valid" screen a user is shown when the key behind their session has
been deleted — three entry points, one screen.

- **Access Keys** — a three-column table: the access key ID (Keystone's credential object carries
  no name or label, so that string is the only way to tell two keys apart), the secret beside it,
  and a delete button. Both values sit in read-only text fields, which is also how they are
  copied — a value selects out of a field perfectly well, so neither carries a copy control of its
  own.
- **Secrets** — concealed by default and fetched only when that key's own **Reveal** is clicked;
  until then the field holds filler of the same length as a real secret, so opening the modal for
  the endpoint fetches no secrets at all. **Hide** discards the value rather than painting over it,
  as do deleting the key and closing the modal. `reveal` is a mutation and the secret is never part
  of `list`, so none of this enters the TanStack Query cache either. What it does not promise: a
  revealed secret is in React state and in the DOM, the same as any value in a controlled input —
  what is ours to decide is how long it stays there.
- **Connection Details** — the S3 endpoint URL and region, each copyable on its own.
- **Create** — the new key's row appears with no page reload and concealed like every other one;
  its secret is read through that row's own Reveal, and a toast names the key and says where to
  find it again. `create` does not return the secret, so `reveal` is the only procedure that ever
  hands one out.
- **No limit** — a user may hold as many keys in a project as they like. Neither Keystone nor RGW
  imposes a ceiling, and all of a user's keys in a project map to the same RGW identity, so an
  extra key grants no extra access and costs no quota; a limit in the dashboard would only be
  Aurora refusing what the backend is willing to do.

**User Stories**

1. As a project member using Ceph object storage, I want to see the access keys I hold in this
   project, so that I know which key an S3 client of mine is configured with.
2. As a project member who has lost the secret of a key I already own, I want to see it again in
   the dashboard, so that I can reconfigure a client without deleting the key and breaking
   everything else that uses it.
3. As a project member reading this screen with someone looking over my shoulder, I want a secret
   to stay concealed until I ask for it, so that opening the modal is not itself a disclosure.
4. As a project member setting up an S3 client, I want the endpoint URL and region next to the
   key, so that I have everything the client needs from one screen.
5. As a project member rotating a key, I want to create a second key while the first one still
   works, so that I can switch clients over and only then remove the old one.
6. As a project member who no longer uses a key, I want to delete it, so that a leaked or
   forgotten key stops granting access to my buckets.
7. As a project member who has just created the project's first key from the empty state, I want
   to be told where that key can be found again, so that the screen I have never seen before is
   not something I have to rediscover by accident.
8. As a project member without permission to create or delete keys, I want to be told so, rather
   than shown a button that fails, so that I know to ask an administrator.

**Acceptance Criteria**

_Discovery and entry points_

- [ ] "Manage Credentials" sits in the overflow menu next to "Create Bucket" whenever the bucket
      list renders — unconditionally, with no check on how many keys the user holds and no
      permission gate, since opening the modal is a read.
- [ ] The "S3 Object Storage: Setup Required" empty state opens that same modal instead of
      silently creating a key and reloading the page.
- [ ] The "S3 Credentials No Longer Valid" screen offers a "Manage Credentials" button, instead
      of telling the user to create new credentials with nowhere to do it.
- [ ] Deleting the last key from inside the modal does not unmount the modal, even though the page
      behind it falls back to the empty state.

_Viewing keys_

- [ ] The modal lists every EC2 credential the caller holds in this project, and only those —
      never another user's, never another project's.
- [ ] Each key shows its access key ID in full, in a read-only field wide enough for the whole
      value, and the value can be selected and copied out of that field.
- [ ] Zero keys reads as an empty state, with the column headers still visible, not as an error.
- [ ] A failure to load the list is reported as an error state, and Connection Details still
      renders.

_Revealing a secret_

- [ ] Nothing fetches or shows a secret except that key's own "Reveal" — not opening the modal,
      not creating a key. Each secret field is concealed and holds filler, not a value anyone
      reading the DOM could mistake for a key.
- [ ] Clicking a key's "Reveal" fetches that one secret — one `reveal` call, for that key only —
      and shows it in full, in a field wide enough for the whole value.
- [ ] "Hide" discards the secret rather than masking it, and a later "Reveal" fetches it again.
- [ ] The field is read-only whether concealed or revealed; the revealed value can be selected and
      copied out of it.
- [ ] A reveal in flight shows progress on its own button and leaves the rest of the modal usable,
      including the other key's "Reveal".
- [ ] A failed reveal is reported once, in the modal's single error message, naming the key it
      belongs to — not as a validation message on the field. The other key is unaffected, and
      clicking "Reveal" again retries.
- [ ] Deleting a key discards its revealed secret along with the row.
- [ ] Closing the modal discards every revealed secret, including when it is closed by Escape or
      by the page rather than by the Close button; reopening starts concealed again.
- [ ] A secret that arrives after the modal has closed is discarded rather than written back into
      state — including when the modal has been reopened by the time it arrives, which must not
      unmask a field nobody asked to see.
- [ ] Secrets are never part of the `list` response and never enter the TanStack Query cache.

_Connection details_

- [ ] The modal shows the S3 endpoint URL and region, each copyable on its own.
- [ ] They render for a user who holds no keys yet.
- [ ] `AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… aws --endpoint-url <endpoint> --region <region>
      s3 ls` succeeds with the values shown.

_Creating_

- [ ] Creating a key adds its row with no page reload, concealed like every other row, and fires
      no `reveal` request on its behalf.
- [ ] The `create` response carries no secret at all — `reveal` is the only procedure that returns
      one.
- [ ] A success toast names the new access key ID and says where the key can be found again.
- [ ] The bucket list behind the modal reflects the project's first key once the modal is closed.
- [ ] "Create Access Key" stays available however many keys the user already holds, and nothing on
      the screen claims a maximum.
- [ ] Creating a key costs one request: the server does not read the existing credential list
      first.
- [ ] A failed create is reported in the modal without closing it.

_Deleting_

- [ ] A key's delete button opens a confirmation dialog on top of the modal, which names the key
      and states that it stops working immediately and cannot be restored.
- [ ] Deleting the last key says so in that dialog: without a key, S3 Object Storage is out of
      reach in the dashboard as well as from any S3 client, the buckets themselves are untouched,
      and a new key restores access to them.
- [ ] Cancelling leaves the key in place; confirming closes the dialog, removes the row and raises
      a toast naming the deleted access key.
- [ ] A spinner replaces that key's delete button while the request is in flight.
- [ ] With more than one key on screen, each delete button says which key it deletes.
- [ ] Deleting a key that is not the last one does not trigger a re-scan of the bucket listing.
- [ ] A failed delete is reported in a toast carrying what the server answered — not in the
      modal's error message, and never as a success.
- [ ] A credential that is already gone answers `NOT_FOUND` rather than being reported as deleted,
      and the key list is refreshed anyway so its row does not stay on screen.
- [ ] A user without the delete permission does not see the delete button.

_Isolation and permissions_

- [ ] Ownership is checked from the rescoped token, never from client input.
- [ ] What the identity service answers is what the caller gets: a 404 reads as "no such key", a
      403 as a permission error, a 401 as an authentication error. The router does not rewrite one
      status into another, in either shape a refusal can arrive in.
- [ ] The one answer the router decides for itself: a credential the identity service does return,
      but which belongs to another user or project, is refused rather than read — its blob is never
      parsed and its secret never leaves the server.
- [ ] Credentials of a type other than `ec2` are treated as absent rather than deleted or parsed.
- [ ] A user who may not create sees no "Create Access Key" button; a user who may not delete sees
      no delete buttons. One message names what they cannot do here and sends them to an
      administrator — whichever of the two permissions is missing, and both in a single message
      when both are.
- [ ] The key list, the endpoint and the region stay visible whatever those two permissions say.
      Reading one's own keys is not gated anywhere in this UI, and someone who can only read is
      exactly who needs the endpoint and region.
- [ ] While the permission check is still in flight both controls stay on screen, disabled, and
      nothing claims a refusal yet.
- [ ] A missing policy rule resolves to "not allowed" for that one permission key and leaves every
      other storage permission in the same batch unaffected.
- [ ] A failed permission *check* reads as "could not verify, try again", not as "you lack
      permission — contact your administrator".

_Escape and in-flight requests_

- [ ] Escape does not close the modal while a create or delete is in flight.
- [ ] A reveal in flight does not block Close, Create or Delete — it belongs to one row, not to
      the modal.
- [ ] The reverse does hold: with a create or delete in flight, nothing in the modal can be
      clicked — Close, the close button, Escape, Create, every delete button and every Reveal.

**Alternatives Considered**

- **Show the secret only once, at creation time, and never again.** Rejected: every current user's
  creation moment has already passed, so it solves nothing for the people who reported this. It
  would also make a lost secret a reason to delete a working key.
- **Return the secret from `list`.** Rejected: it would put every secret of every key into the
  TanStack Query cache, where it survives the modal and is visible in devtools. A separate
  `reveal` *mutation* per key keeps secrets out of the cache entirely.
- **Show every secret outright, fetched as the modal opens.** Built first, and the argument for it
  is real: every key on this screen belongs to the caller, and the BFF reads the same secret out of
  Keystone to sign every Ceph request, so a reveal control guards nothing the session does not
  already hold. Dropped on design review all the same — a secret rendered without being asked for
  is a secret on screen during a screen share, and fetching both of them to open a modal someone
  opened for the endpoint is work nobody asked for.
- **Juno's `SecretText` as the reveal control.** Prototyped. It conceals by drawing a blurred cover
  over a textarea that still holds the value — paint rather than a boundary, unless the fetch is
  deferred as well — and bundles copy and clear controls this screen does not want. An
  `InputGroup` of a read-only `type="password"` field with its own Reveal/Hide button says exactly
  what is meant and nothing more.
- **A "currently active" badge on the key the BFF signs with.** Rejected: all of a user's keys in a
  project map to the same RGW identity, so the badge would label an implementation detail as if it
  were a property of the key.

**Out of scope / known limitations**

- Naming or labelling keys. Keystone's credential object has no field for it — only the `blob`,
  which we compose — and whether Keystone tolerates an extra key there is unverified against a
  real deployment. Until it is, two keys are told apart by their access key ID alone.
- Choosing which key the BFF signs with, and rotation by switching an active key. The choice is
  made deterministic (sorted by credential ID) rather than dependent on Keystone's response order,
  but there is still no concept of an active key.
- Keeping a revealed secret out of client memory altogether. Juno's `TextInput` is controlled and
  mirrors whatever it is handed into its own state, so a displayed secret is in React state and in
  the DOM regardless of who holds it. The reachable property is lifetime, not absence.
- Swift, which does not use EC2 credentials.

**Open points**

- Where the modal's single error message belongs on the screen. It currently sits above the
  sections; placement is still open.
- The secret field is the first `InputGroup` in the dashboard pairing an input with its own action
  button — the only other one (`ListToolbar/FiltersInput.tsx`) groups two inputs — and Juno still
  marks `InputGroup` as WIP. Worth agreeing whether this becomes the general pattern for "value
  plus inline action", which today is `ClipboardText`.
- Overall credential-handling patterns across the dashboard: this is an interim solution for Ceph
  S3 specifically, not a general answer for credentials.

**Additional Context**

- The "S3 Object Storage: Setup Required" screen is rebuilt on Juno's `Status` component, the same
  one the bucket list's other full-page states already use, rather than hand-rolled markup.
- The success message on the first key creation names where the key can be found again, per
  design feedback.
- Only the two mutations are permission-gated (`storage:credentials:create`,
  `storage:credentials:delete`). There is no permission key for reading credentials, and none is
  added here: the convention in this codebase is that reads are never gated (documented in
  `useCephPermissions`), Keystone already answers with the caller's own credentials and no others,
  and hiding the list would leave a user without those two permissions looking at a modal with
  nothing in it — no keys, no endpoint, no region — which is the one thing they came for.
- New permission key `storage:credentials:delete`. Operators with a forked `storage.json` should
  add `"storage:credential_delete": "rule:storage_viewer"` (or their own equivalent rule);
  without it the delete action stays hidden and everything else keeps working.
- That last sentence was not true before this change, which is why adding a permission key is worth
  a line here at all. `canUser` evaluates the whole batch of keys in one pass, and a rule missing
  from the loaded policy file threw — failing the batch rather than the key. `useCephPermissions`
  asks for around twenty keys at once, so one unknown rule hid every Ceph action, not the one it
  governs, and `storage:credential_delete` would have walked straight into it on any forked policy
  file. A missing rule now answers "not allowed" for its own key and leaves the rest of the batch
  alone.
