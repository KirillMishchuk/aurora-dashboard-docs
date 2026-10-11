---
type: runbook
date: 2026-09-29
plan: plans/2026-09-29-ceph-s3-credentials-management-ui.md
---
# Runbook: probe "label in the EC2 credential blob"

**Date:** 2026-09-29 · **For:** plan [2026-09-29-ceph-s3-credentials-management-ui.md](../plans/2026-09-29-ceph-s3-credentials-management-ui.md) · **Where to run:** a remote machine with network access (VPN/bastion)

## Why

An EC2 credential in Keystone has no name, no description, and no tags — the whole object is
`{id, type, user_id, project_id, blob}`. The only place a human-readable label
("backups", "CI", "laptop") can go is the `blob` itself, which
Aurora composes on its own:

```json
{ "access": "…", "secret": "…", "label": "backups" }
```

On the Aurora side this is safe — verified in the code: `list`
(`ec2CredentialRouter.ts:71-77`), `create` (`:134-140`) and
`resolveEC2Credential.ts` do `JSON.parse` and then explicitly pick fields into a
projection under `safeParse`, i.e. an extra key passes through untouched.

Unverified, and checked by this runbook:

1. **Will Keystone accept** a credential with an extra field in the blob, and **will it keep** it.
2. **Will it break** authentication — the S3 signature goes to RGW, which forwards it
   to Keystone at `/v3/ec2tokens`, which reads the same blob.

The cost of a mistake is high: if there is validation after all, it is not the display that breaks but
the key itself — the user gets a credential that does not work. So we verify
by hand before building labels into the plan.

## What you need on the machine

| Tool | Why | If missing |
| --- | --- | --- |
| `curl` | all requests to Keystone | available everywhere |
| `jq` | building/parsing JSON | `sudo apt install jq` / `sudo dnf install jq`, or see "Without jq" at the end |
| `openssl` | generate random access/secret | available everywhere |
| `aws` (AWS CLI v2) | only for part 2 | `pip3 install --user awscli`, or see "Installing AWS CLI" |

Check in one line:

```bash
for t in curl jq openssl aws; do command -v "$t" >/dev/null && echo "$t: ok" || echo "$t: MISSING"; done
```

Without `aws` you can run part 1 — it answers the main question. Part 2
is desirable but does not block the decision.

## Before you start

**The probe creates a real, working key for your project.** Not a test one — the
one you work in. Hence three rules:

1. **Write down `CRED_ID` as soon as you get it.** If the session drops, the key
   will stay alive in Keystone. The "Cleanup" section has a command that finds
   forgotten probe credentials by their label.
2. **Do not write anything to files.** No `~/.aws/credentials`, no temporary files with
   the token — everything lives only in the current shell's environment variables. On a shared
   machine this matters.
3. **Disable shell history for the duration of the probe** — the password is entered via
   `read -rs` and will not end up in history, but it is better not to leave the rest either:

   ```bash
   set +o history        # bash
   unset HISTFILE        # zsh / just in case
   ```

   To restore — `set -o history`, or simply close the session.

The environment is **QA** (`qa-de-1`), not prod. Values are taken from
`apps/dashboard/.env` of the working copy: `IDENTITY_ENDPOINT=https://identity-3.qa-de-1.cloud.sap/v3`,
`CEPH_REGION=ceph-objectstore-ec-st1-qa-de-1`. If the remote machine has a different
environment, substitute your own.

## Part 1. Does Keystone accept the extra field

### Step 1. Connectivity

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 https://identity-3.qa-de-1.cloud.sap/v3
```

- `200` or `300` — good, move on.
- `000` — no network to Keystone: VPN is not up, or the machine is in the wrong segment.
  Stop here; nothing further will work.

### Step 2. Project-scoped token

`PROJECT_ID` is taken straight from the dashboard URL: `/projects/<PROJECT_ID>/storage/...`.
`USER_DOMAIN` is the domain you log in to (e.g. `monsoon3`).

```bash
IDENTITY=https://identity-3.qa-de-1.cloud.sap/v3
USER_NAME=<your login>
USER_DOMAIN=<your domain>
PROJECT_ID=<project id from the dashboard URL>

read -rs -p "password: " OS_PASSWORD; echo

RESP=$(curl -si -X POST "$IDENTITY/auth/tokens" -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$USER_NAME" --arg d "$USER_DOMAIN" --arg p "$OS_PASSWORD" --arg pid "$PROJECT_ID" \
    '{auth:{identity:{methods:["password"],password:{user:{name:$u,domain:{name:$d},password:$p}}},scope:{project:{id:$pid}}}}')")

TOKEN=$(printf '%s' "$RESP" | tr -d '\r' | awk 'tolower($1)=="x-subject-token:"{print $2}')
USER_ID=$(printf '%s' "$RESP" | sed -n '/^{/,$p' | jq -r '.token.user.id')

echo "token: ${TOKEN:+ok}   user_id: $USER_ID"
```

Expect `token: ok` and a non-empty `user_id`.

If empty — look at the first line of the response and the error text:

```bash
printf '%s' "$RESP" | head -1
printf '%s' "$RESP" | sed -n '/^{/,$p' | jq -r '.error.message? // empty'
```

`401` — login/password/domain. `404` on scope — wrong `PROJECT_ID`.
`403` — the user has no role in this project.

The password is no longer needed; remove it from the shell:

```bash
unset OS_PASSWORD
```

### Step 3. Create a probe credential with a label

```bash
ACCESS=$(openssl rand -hex 20 | tr 'a-z' 'A-Z')
SECRET=$(openssl rand -base64 40)

CRED=$(curl -s -X POST "$IDENTITY/credentials" \
  -H "X-Auth-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg a "$ACCESS" --arg s "$SECRET" --arg p "$PROJECT_ID" --arg u "$USER_ID" \
    '{credential:{type:"ec2",project_id:$p,user_id:$u,blob:({access:$a,secret:$s,label:"aurora-label-probe"}|tostring)}}')")

CRED_ID=$(printf '%s' "$CRED" | jq -r '.credential.id // empty')
echo "CRED_ID=$CRED_ID"
```

**Write `CRED_ID` down somewhere outside the shell right now.** This is what will have to be
deleted.

If `CRED_ID` is empty — Keystone rejected the request, and that is already the answer:

```bash
printf '%s' "$CRED" | jq .
```

The access/secret format here is exactly the same as what Aurora generates
(`ec2CredentialRouter.ts:110-111`): 20 random bytes in uppercase hex and
40 random bytes in base64. This is intentional — the probe must be indistinguishable from a
production key in everything except the extra field.

### Step 4. Re-read and confirm the label is stored

It is critical to do this as a separate request: the POST response may simply echo what
we sent, whereas we care about what actually landed in the database.

```bash
curl -s "$IDENTITY/credentials/$CRED_ID" -H "X-Auth-Token: $TOKEN" | jq -r '.credential.blob'
```

**How to read the result:**

| What we see | Conclusion |
| --- | --- |
| `{"access":"…","secret":"…","label":"aurora-label-probe"}` | Keystone stores the field — the main question is answered positively |
| blob without `label` | the field is silently stripped — labels in the blob are impossible, idea closed |
| POST returned 400/validation error | Keystone validates the blob — idea closed |

If the label did not survive — go straight to "Cleanup"; part 2 is not needed.

## Part 2. Does the S3 signature break

Answers the second question: RGW forwards the signature to Keystone at `/v3/ec2tokens`, and
that reads the same blob. If the extra field trips up this path, the key will
be created but will not work, which is worse than having no labels at all.

### Step 5. Find the S3 endpoint

The service in the catalog is called `ceph` (`cephProcedure.ts:24`), and the
`/swift/...` suffix must be cut off — exactly what `resolveS3Config` does:

```bash
S3=$(printf '%s' "$RESP" | sed -n '/^{/,$p' \
  | jq -r '.token.catalog[] | select(.name=="ceph") | .endpoints[] | select(.interface=="public") | .url' \
  | head -1 | sed 's#/swift/.*##')

echo "S3=$S3"
```

Empty — means this project's catalog has no `ceph` service; then Ceph itself in the
dashboard does not work for this project either, check `PROJECT_ID`.

### Step 6. Hit S3 with the probe key

Pass the keys via the environment of a single command — so nothing settles in
`~/.aws/`:

```bash
AWS_ACCESS_KEY_ID="$ACCESS" AWS_SECRET_ACCESS_KEY="$SECRET" \
AWS_EC2_METADATA_DISABLED=true \
  aws --endpoint-url "$S3" --region ceph-objectstore-ec-st1-qa-de-1 s3 ls
```

| What we see | Conclusion |
| --- | --- |
| a list of buckets, or empty output with no error | the signature passed — the extra field has no effect |
| `InvalidAccessKeyId` | Keystone did not recognize the key on this path — idea closed |
| `SignatureDoesNotMatch` | first double-check the region and that `$SECRET` was not mangled by the shell (it can contain `+` and `/`), and only then draw a conclusion |
| `Could not connect` | no network to RGW, even though Keystone is reachable — this is about the network, not the label |

## Cleanup (mandatory)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "$IDENTITY/credentials/$CRED_ID" -H "X-Auth-Token: $TOKEN"
```

`204` — deleted. `404` — already deleted, also fine.

Check that no probe credentials remain (including from an interrupted attempt):

```bash
curl -s "$IDENTITY/credentials?user_id=$USER_ID&type=ec2" -H "X-Auth-Token: $TOKEN" \
  | jq -r '.credentials[] | select(.blob | contains("aurora-label-probe")) | .id'
```

The output must be empty. If something is found — delete it with the same DELETE using that
`id`.

While at it, make sure your **production** credentials are in place and there are as many of them as
there were before the probe:

```bash
curl -s "$IDENTITY/credentials?user_id=$USER_ID&type=ec2" -H "X-Auth-Token: $TOKEN" \
  | jq -r --arg p "$PROJECT_ID" '[.credentials[] | select(.type=="ec2" and .project_id==$p)] | length'
```

And clean up the shell:

```bash
unset TOKEN ACCESS SECRET CRED CRED_ID RESP
set -o history
```

## What to report back

Two lines are enough:

1. Whether `"label":"aurora-label-probe"` survived in the re-read blob (step 4).
2. Whether `aws s3 ls` succeeded (step 6), and if not — with exactly which error.

**Do not send the secret, access key, or token** — they have no bearing on the
decision, and forwarding them means spreading them across logs and chats.

## Appendix

### Installing AWS CLI, if it is missing

```bash
# Linux x86_64, official installer, no root:
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install -i ~/.local/aws-cli -b ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"

# or, if pip is available:
pip3 install --user awscli
```

### Without jq

`jq` is used only for building and parsing JSON; `python3` is available almost everywhere and
replaces it. Token:

```bash
BODY=$(python3 -c 'import json,sys,os
print(json.dumps({"auth":{"identity":{"methods":["password"],"password":{"user":{
 "name":os.environ["USER_NAME"],"domain":{"name":os.environ["USER_DOMAIN"]},
 "password":os.environ["OS_PASSWORD"]}}},"scope":{"project":{"id":os.environ["PROJECT_ID"]}}}}))')
```

(the variables must be exported: `export USER_NAME USER_DOMAIN PROJECT_ID OS_PASSWORD`)

Parsing the blob:

```bash
curl -s "$IDENTITY/credentials/$CRED_ID" -H "X-Auth-Token: $TOKEN" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["credential"]["blob"])'
```

### If the probe passed — what changes in the plan

Do not do this in advance, only after a positive result:

- Decision 6 (limit of 2 keys) — raise to 5. The limit of 2 was modeled on AWS
  precisely because keys are interchangeable and two are needed only for zero-downtime
  rotation; named keys acquire a purpose, and two becomes an
  arbitrary number.
- Decision 10 (modal contents) — the label becomes the primary way to tell
  keys apart; showing the full access key stays, but moves to the background.
- `ec2CredentialSchema` — `label: z.string().max(…).optional()`; being optional is
  mandatory: all existing credentials, as well as those created via
  `openstack ec2 credentials create`, have no label and never will.
- `create` — accept a label as input; editing a label is
  `PATCH /v3/credentials/{id}` overwriting the **entire** blob, i.e. the server
  must read the current blob and write it back together with the secret.
