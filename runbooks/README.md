---
type: index
---
# runbooks

Step-by-step manual procedures for checks that can't be done from this machine or from the code alone — typically a probe against a live OpenStack/Ceph environment, run by hand on the remote machine (VPN/bastion access). Each runbook exists to settle one open question a plan depends on, before the plan commits to an approach.

- **Who writes here:** no skill writes here automatically. A runbook is written on request while working on a plan, when the plan rests on an assumption that only a live environment can confirm. The plan links to its runbook, and the runbook links back to the plan.
- **Naming:** `YYYY-MM-DD-<kebab-slug>.md`, the date matching the plan it serves.
- **Shape** (follow the existing one):
  - a header line — date · the plan it's for · where to run it;
  - **Why** — the question being settled and the cost of guessing wrong;
  - **What you need** and **Before you start** — tools, env vars, access;
  - numbered **steps**, each with the exact command and the expected output;
  - **Cleanup (mandatory)** — remove everything the probe created and verify nothing real was touched;
  - **What to report back** — the few facts the plan needs; never secrets, keys or tokens.
- **Lifecycle:** written once, executed by hand, the outcome recorded in the plan it serves. Kept afterwards as a record of how the conclusion was reached; not updated retroactively.

| Date | Runbook | For plan |
| --- | --- | --- |
| 2026-09-29 | [EC2 credential label probe](./2026-09-29-ec2-credential-label-probe.md) — does Keystone accept and keep an extra `label` field in an EC2 credential blob, and does S3 signing still work | [2026-09-29-ceph-s3-credentials-management-ui.md](../plans/2026-09-29-ceph-s3-credentials-management-ui.md) |
