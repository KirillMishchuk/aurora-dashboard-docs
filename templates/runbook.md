---
type: runbook
date: "{{date}}"
plan: plans/<plan-file>.md
---
# Runbook: {{title}}

**Date:** {{date}} · **For:** plan [<plan title>](../plans/<plan-file>.md) · **Where to run:** <remote machine / local / DevStack>

## Why

<The one open question this runbook settles, and what it costs if we guess wrong.>

## What you need on the machine

- <tools, env vars, access>

## Before you start

- <what to export / check first>

## Steps

### Step 1. <name>

```bash
<command>
```

Expected: <output>

## Cleanup (mandatory)

```bash
<remove everything the probe created>
```

Verify nothing real was touched: <check>

## What to report back

1. <fact the plan needs>

**Never send secrets, keys or tokens back** — only the facts above.
