## Summary

User feedback from `dashboard-aurora.eu-de-1.cloud.sap`:

> The policy editor does not work with policies who are using the multi-tenancy syntax to grant other tenants access to the buckets, as they don't pass the principal validation. This also applies to existing policies, which are not even displayed even when they are actively used.

Both halves of that report come from one line — the Principal ARN check in `bucketPolicyStatementSchema`:

```ts
!/^arn:aws:iam::\d{12}:(?:root|user\/.+|role\/.+)$/.test(arn)
```

`\d{12}` is an AWS account ID. Ceph RGW never puts one there. Per the RGW docs the account field of a principal ARN holds a tenant name, an RGW account ID (`RGW` + 17 digits), or nothing at all — and in a Keystone-backed deployment the tenant is the project UUID. Every principal a user of this deployment can legitimately write fails a check that only accepts a form that cannot occur here.

**Why existing policies vanish.** `bucketPolicy.get` ran the same schema over what RGW returned. The resulting `ZodError` isn't an S3 error name, so `mapS3ErrorToTRPCError` mapped it to `INTERNAL_SERVER_ERROR`, and `BucketPolicyModal` hides the editor entirely whenever the query errors. A live policy that RGW is enforcing right now became invisible and uneditable — in the one screen meant to fix it — even though the raw document was already in hand.

## Changes Made

**Server — `types/ceph.ts`**

- Removed the AWS-only principal ARN regex. Principal contents are no longer validated here; RGW is the authority on its own grammar and answers `MalformedPolicy` for what it won't accept. The structural checks (Principal is a string or an object, and that object carries at least one of `AWS`/`Service`/`Federated`) stay.

**Server — `routers/ceph/bucketPolicyRouter.ts`**

- `get` no longer validates. `policyText` is always returned exactly as stored; `policy` is a best-effort parse and is `null` when the document doesn't fit our schema or isn't JSON at all. Reads can no longer fail over a shape we don't model.
- `validateResourceARNsMatchBucket` accepts the tenant-qualified resource form `arn:aws:s3::TENANT:bucket` alongside `arn:aws:s3:::bucket`. The bucket segment is still compared against the target bucket, so the policy-confusion guard is intact. The tenant segment itself is not checked against the current project: the policy is attached to *this* bucket, so a resource naming another tenant's bucket grants nothing, and hard-coding what a tenant looks like is the assumption that caused this bug.

**Tests**

- `ceph.test.ts`: the "reject an invalid AWS ARN" case is replaced by a table of the five principal forms RGW documents (tenant UUID, tenant name, `:subuser` suffix, empty tenant, RGW account ID) plus a tenant root, a mixed-form array, and a case proving non-string values are still rejected.
- `bucketPolicyRouter.test.ts`: `get` returns a tenant-principal policy; `get` still returns the raw text when the stored document doesn't fit the schema and when it isn't valid JSON; `set` accepts tenant-qualified principals and a tenant-qualified resource ARN, and still rejects a resource naming a different bucket.

## Note for reviewers

The new `set` tests use their own bucket names on purpose. `checkPolicySetRateLimit` is keyed by `project:bucket` and counts every attempt, including ones rejected by validation later, and the existing `set` suite already sits at exactly the 10-call budget for `my-test-bucket` — adding calls there silently rate-limits the tests below. Worth tightening separately (per-test key reset), out of scope here.

## Not changed

- No client changes. `BucketPolicyModal` already falls back to rendering `policyText` when it can't be parsed, so fixing the read on the server is enough.
- `validatePolicySemantics` still rejects any `Deny s3:*`/`Deny *` outright. That's a legitimate pattern when the deny is narrowed by a `Condition`, but it is not what this report is about.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
