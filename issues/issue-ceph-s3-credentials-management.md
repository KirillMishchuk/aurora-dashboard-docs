# [Feature](storage): manage S3 access keys for Ceph object storage

**Description**

Ceph object storage is used through S3 access keys (Keystone EC2 credentials), but the dashboard
has no screen for them. A user can see their buckets and objects, and cannot see, recover, rotate
or remove the key those buckets are reached with.

Add a **Manage Credentials** modal on the Ceph bucket list that lists the access keys the user
holds in the project, reveals a secret on request, creates and deletes keys, and shows the S3
endpoint and region next to them.

**Problem Statement**

Reported on `/projects/<id>/storage/ceph/containers` in a project that already had a working key:

> I have no option to see or manage my credentials.

Three separate gaps sit behind that sentence:

1. **No way in.** The only credentials UI is the "S3 Object Storage: Setup Required" empty state,
   and the bucket list renders it on exactly one condition — the backend answering
   `NO_CEPH_CREDENTIALS`. Once a user has a key, that screen is unreachable for the rest of the
   project's life.
2. **The secret is shown once and thrown away.** That empty state creates a key, receives
   `{ access, secret }`, discards the secret, and reloads the page. A user who missed that moment,
   or who joined a project someone else set up, has no way to recover it — and no way to rotate,
   because there is no delete either.
3. **The endpoint and region are nowhere in the UI.** They are known only to the server. An access
   key on its own does not let anyone configure an S3 client.

The secret is recoverable: Keystone EC2 credentials are not Application Credentials — the blob is
stored encrypted and decrypted on every read, and the owner may read their own under the default
policy. Aurora's own BFF already performs that read on every single Ceph request in order to sign
the S3 call, so showing it to its owner exposes nothing that was not already crossing the BFF.

**Proposed Solution**

A **Manage Credentials** modal, reachable from the overflow ("More Actions") menu next to
"Create Bucket", from the rewritten "Setup Required" empty state, and from the "invalid
credentials" error branch — three entry points, one screen.

- **Access Keys** — one card per key: the access key ID in full (Keystone's credential object
  carries no name or label, so that string is the only way to tell two keys apart), a delete
  button, and the secret in a Juno `SecretText`, concealed until the user reveals it.
- **Connection Details** — the S3 endpoint URL and region, each copyable on its own.
- **Create** — the new key's secret is shown immediately, in a field that comes up revealed,
  with a toast that also says where to find the key again.
- **Limit** — at most two keys per user per project, mirroring AWS's own two-access-key limit:
  enough to rotate without downtime, not enough to accumulate keys nobody can account for.

**User Stories**

1. As a project member using Ceph object storage, I want to see the access keys I hold in this
   project, so that I know which key an S3 client of mine is configured with.
2. As a project member who has lost the secret of a key I already own, I want to reveal it again
   from the dashboard, so that I can reconfigure a client without deleting the key and breaking
   everything else that uses it.
3. As a project member setting up an S3 client, I want the endpoint URL and region next to the
   key, so that I have everything the client needs from one screen.
4. As a project member rotating a key, I want to create a second key while the first one still
   works, so that I can switch clients over and only then remove the old one.
5. As a project member who no longer uses a key, I want to delete it, so that a leaked or
   forgotten key stops granting access to my buckets.
6. As a project member who has just created the project's first key from the empty state, I want
   to be told where that key can be found again, so that the screen I have never seen before is
   not something I have to rediscover by accident.
7. As a project member without permission to create or delete keys, I want to be told so, rather
   than shown a button that fails, so that I know to ask an administrator.
8. As an operator running my own policy files, I want a new permission key to degrade to "not
   allowed" for that one action, so that a rule I have not added yet does not hide unrelated
   actions elsewhere in the storage UI.

**Acceptance Criteria**

_Discovery and entry points_

- [ ] With at least one key, "Manage Credentials" is available in the overflow menu next to
      "Create Bucket" on the Ceph bucket list.
- [ ] With no keys, the "S3 Object Storage: Setup Required" empty state opens the same modal
      instead of silently creating a key and reloading the page.
- [ ] The "invalid credentials" error state offers a way into the same modal instead of prose
      with no action.
- [ ] Deleting the last key from inside the modal does not unmount the modal, even though the page
      behind it falls back to the empty state.

_Viewing keys_

- [ ] The modal lists every EC2 credential the caller holds in this project, and only those —
      never another user's, never another project's.
- [ ] Each key shows its access key ID in full and copyable.
- [ ] Zero keys reads as an empty state, not as an error.
- [ ] A failure to load the list is reported as an error state, and Connection Details still
      renders.

_Revealing a secret_

- [ ] Every secret is concealed when the modal opens.
- [ ] A secret is fetched only when the user reveals that key — opening the modal to copy the
      endpoint issues no secret request at all.
- [ ] Revealing one key does not fetch or reveal the other.
- [ ] Hiding and revealing the same key again issues no second request.
- [ ] Copy is unavailable while the field is still empty.
- [ ] A failed reveal is reported on that key's own field, leaves the other key working, and a
      further reveal retries it.
- [ ] Closing the modal clears every revealed secret; reopening starts concealed again.
- [ ] No secret is ever written to the TanStack Query cache.

_Connection details_

- [ ] The modal shows the S3 endpoint URL and region, each copyable on its own.
- [ ] They render for a user who holds no keys yet.
- [ ] `AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… aws --endpoint-url <endpoint> --region <region>
      s3 ls` succeeds with the values shown.

_Creating_

- [ ] Creating a key shows its secret immediately, in a field that is already revealed, with no
      page reload and without spending a second request to read back what was just returned.
- [ ] A success toast names the new access key ID and says where the key can be found again.
- [ ] The bucket list behind the modal reflects the project's first key once the modal is closed.
- [ ] "Create Access Key" is disabled once the user holds two keys in the project, and the rule is
      stated on the screen rather than only at the moment of failure.
- [ ] The server refuses a third key independently of the UI, with `CONFLICT` /
      `EC2_CREDENTIAL_LIMIT_REACHED`, and the modal reports it without closing.

_Deleting_

- [ ] A key can be deleted from its own card, a toast names the deleted access key, and the card
      goes.
- [ ] A spinner replaces that key's delete button while the request is in flight.
- [ ] Deleting a key that is not the last one does not trigger a re-scan of the bucket listing.
- [ ] Deleting a credential that is already gone is reported as success, not as an error.
- [ ] A user without the delete permission does not see the delete button.

_Isolation and permissions_

- [ ] Ownership is checked from the rescoped token, never from client input.
- [ ] A credential the caller does not own answers `NOT_FOUND`, not `FORBIDDEN`, so the answer
      alone cannot be used to confirm that a credential ID exists.
- [ ] Credentials of a type other than `ec2` are treated as absent rather than deleted or parsed.
- [ ] A missing policy rule resolves to "not allowed" for that one permission key and leaves every
      other storage permission in the same batch unaffected.
- [ ] A failed permission *check* reads as "could not verify, try again", not as "you lack
      permission — contact your administrator".

_Escape and in-flight requests_

- [ ] Escape does not close the modal while a create or delete is in flight.
- [ ] A secret that arrives after the modal has closed is discarded rather than written back into
      state.

**Alternatives Considered**

- **Show the secret only once, at creation time, and never again.** Rejected: every current user's
  creation moment has already passed, so it solves nothing for the people who reported this. It
  would also make a lost secret a reason to delete a working key.
- **Return the secret from `list`.** Rejected: it would put every secret of every key into the
  TanStack Query cache, where it survives the modal and is visible in devtools. A separate
  `reveal` *mutation* per key keeps secrets out of the cache entirely.
- **Fill every `SecretText` as the modal opens and let the component conceal them.** Rejected:
  `SecretText` conceals by drawing a blurred cover over a textarea that still holds the value, so
  this would put every key in the DOM behind something that is not a boundary.
- **A "currently active" badge on the key the BFF signs with.** Rejected: all of a user's keys in a
  project map to the same RGW identity, so the badge would label an implementation detail as if it
  were a property of the key.

**Out of scope / known limitations**

- Naming or labelling keys. Keystone's credential object has no field for it — only the `blob`,
  which we compose — and whether Keystone tolerates an extra key there is unverified against a
  real deployment. The limit stays at two until it is.
- Choosing which key the BFF signs with, and rotation by switching an active key. The choice is
  made deterministic (sorted by credential ID) rather than dependent on Keystone's response order,
  but there is still no concept of an active key.
- Swift, which does not use EC2 credentials.

**Open points**

- Delete currently happens on the click, with no confirmation step — matching how a row is removed
  from the metadata tables that live inside modals elsewhere in the dashboard. Worth confirming
  this is the pattern we want for something that revokes access, rather than a confirm step.
- Overall credential-handling patterns across the dashboard: this is an interim solution for Ceph
  S3 specifically, not a general answer for credentials.

**Additional Context**

- The modal uses the Juno `SecretText` component for the secret, per design feedback.
- The success message on the first key creation names where the key can be found again, per the
  same feedback.
- New permission key `storage:credentials:delete`. Operators with a forked `storage.json` should
  add `"storage:credential_delete": "rule:storage_viewer"` (or their own equivalent rule);
  without it the delete action stays hidden and everything else keeps working.
