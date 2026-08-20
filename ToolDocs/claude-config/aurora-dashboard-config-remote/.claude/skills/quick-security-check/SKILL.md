---
name: quick-security-check
description: >-
  Fast, focused security audit of one specific file or component in
  aurora-dashboard via the security-reviewer subagent. Use when the user
  wants a quick security pass on a single file rather than a full
  triple-review or a broad security-review of the whole branch.
---

# Quick security check

Single-file, single-agent audit — for a full-branch review use
`/security-review` instead.

## Steps

1. **Get the target.** Use what the user specified. If none was given, ask
   which file/component to check — don't guess a default. A "component" in
   this codebase is often a directory (`index.tsx` + subcomponents + a
   colocated `types.ts`/test file), not one file — if the user names a
   component rather than a path, resolve it to its actual directory and
   gather all its source files (skip `*.test.ts(x)`, they're not attack
   surface). If the given path doesn't exist, say so and stop rather than
   launching the reviewer on a bad path.
2. **Launch `security-reviewer`** (foreground) with the target file(s) and
   instruction to be maximally thorough on this small scope: auth/authorization
   (correct tRPC procedure builder, permission checks via
   `createPermissionRouter`/oslo.policy), input validation (Zod schemas),
   secrets/credential handling, and any injection/XSS surface actually
   reachable in this stack. Ask it to flag even borderline/theoretical risks
   for this focused pass, and note anything it can't fully assess from a
   single file in isolation (e.g. a procedure builder's guarantees defined
   elsewhere).
3. **Report** the overall risk level and findings list as returned. If zero
   findings, say so plainly rather than padding the report.
