# PR-ревью (до мержа)

Ревью PR *до* мержа — черновые находки, которые питают пункты в [`../plans/`](../plans/) (см. процедуру `implement-plan`). Не путать с [`../aurora-dashboard-kb/prs/`](../aurora-dashboard-kb/prs/): там отчёты по PR, которые уже существуют как оформленное целое (открыты или смержены) — для долгосрочной справки. Здесь — рабочий, предмерджевый разбор, который устаревает по мере правок и не обновляется задним числом.

| PR | Ветка | Дата | Находки | Файл |
| --- | --- | --- | --- | --- |
| [#1178](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1178) | `kiryl-ceph-lifecycle-rules` vs `main` | 20.08.2026 | Ceph Lifecycle Rules UI — 5 correctness-багов (валидация Days-полей, Abort+tag-filter server gap, malformed-rule GET failure, order-sensitive freshness check), 3 дублирования (rate limiter, delete-модалки, `normalizeFilter`), 1 dead-code/test-parity, 1 memoization gap; фиксы отслеживаются в [`../plans/2026-08-20-pr-1178-code-review-fixes.md`](../plans/2026-08-20-pr-1178-code-review-fixes.md) | [pr-1178-review.md](./pr-1178-review.md) |
