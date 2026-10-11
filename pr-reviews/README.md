---
type: index
---
# PR reviews (pre-merge)

Reviews of PRs *before* merge — draft findings. Not to be confused with [`../aurora-dashboard-kb/prs/`](../aurora-dashboard-kb/prs/): those are reports on PRs that already exist as a finished whole (open or merged), kept for long-term reference. This folder holds the working, pre-merge analysis, which goes stale as the PR changes and is not updated retroactively.

**Who writes here:** the `triple-review` skill (security + performance + architecture reviewers) saves its combined report as `pr-<number>-review.md` (or `<branch-slug>-review.md` before a PR exists) and adds/updates the row in the table below. One file per PR — a re-run overwrites it with a `## Supersedes` note; older versions are in git history. Nothing is posted to GitHub. The two August reviews below predate this and are `/code-review` output saved by hand.

| PR | Branch | Date | Findings | File |
| --- | --- | --- | --- | --- |
| [#1207](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1207) | `kiryl-ceph-permissions` vs `main` | 2026-08-28 (updated, was 2026-08-26) | Ceph Lifecycle Rules + permission gating — re-review at new head `d01e15c4`: the old finding about `mutationsBlocked` in Create Lifecycle Rule is resolved; the object-size-filter finding is no longer in this PR's diff (the file is now identical to main) — out of scope; new finding (confidence 80): a new doc comment in `permissionRouter.ts` claims that EC2 credentials + bucket policy provide real authorization for ceph mutations (bucket policy/CORS/lifecycle/versioning/version restore), but no ceph router performs a server-side permission check — only `cephProtectedProcedure` (any EC2 credential present in the project); 6 findings filtered out (score < 80). Not posted to the PR. | [pr-1207-review.md](./pr-1207-review.md) |
| [#1178](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1178) | `kiryl-ceph-lifecycle-rules` vs `main` | 2026-08-20 | Ceph Lifecycle Rules UI — 5 correctness bugs (Days field validation, Abort+tag-filter server gap, malformed-rule GET failure, order-sensitive freshness check), 3 duplications (rate limiter, delete modals, `normalizeFilter`), 1 dead-code/test-parity, 1 memoization gap; fixes tracked in [`../plans/2026-08-20-pr-1178-code-review-fixes.md`](../plans/2026-08-20-pr-1178-code-review-fixes.md) | [pr-1178-review.md](./pr-1178-review.md) |
