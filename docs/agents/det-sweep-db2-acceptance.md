# Det Sweep Db2 acceptance, measured (#5882, 2026-10-24)

Measured from `det-sweep.yml` run history with `gh api repos/.../actions/workflows/det-sweep.yml/runs` and each run's
jobs. Re-measure with the same calls; "job minutes" is a db2 job's `started_at` to `completed_at`, which slightly
overstates the budget's "start to sweep end" (`det_sweep_timing.BUDGET_SECONDS`).

**Window.** The runs API returns 1000 runs at most, so the sample reaches back to 2026-10-23T01:27Z (about 46 h), not 7
days. 149 runs ran db2 jobs; 124 had every db2 job succeed. No run has run a db2 shard since #6545 merged (22:41Z); the
only later det-sweep runs skipped the db2 job. So the numbers below describe main just before #6545, which only changed
the Db2 pool size per shard, not the shard count.

| Acceptance | Result | Met |
|---|---|---|
| No db2 job times out | 437 db2 jobs: 378 success, 57 cancelled (superseded pushes), 2 failures; no "exceeded the maximum execution time". The 2 failures (run 39914231229) failed at "Download the plan's durations", not a timeout | yes, for the 46 h sampled |
| Every Db2 case has a measured duration | 81 of 81 Db2 cases have an entry in `tests/equivalence/det_sweep_durations.json`; run 40139171029 reported 0 unmeasured cases | yes |
| Every db2 shard under 15 min | 3-shard plans (65 runs): slowest shard at or over 15 min in 49, median slowest 15.9 min, max 23.9. 5-shard plans (29 runs): over 15 min in 1, median slowest 12.2 | **no** |
| Slowest shard within 1.3x of the fastest | 3-shard plans: ratio over 1.3 in 16 of 65 (median 1.19). 5-shard plans: 14 of 29 (median 1.30) | **no** |

Run 40139171029 (`db2_cases: all`, 81 cases, 3 shards) is a full sweep. It shows how the miss happens: the plan balances
planned seconds almost exactly (2819 / 2818 / 2850), but the measured case seconds were 2340 / 1542 / 2228, so the
sweeps took 756 / 476 / 699 s (1.59x) and the jobs 914 / 673 / 913 s. Case durations move 30-50% run to run (for
example `genapp-lgucus01` 66 s recorded, 28 s measured; `genapp-lgipdb01` 126 s recorded, 168 s measured), and one
shard also holds the 445 s `cbsa-bankdata` case, so a shard's wall time is not its sum of case seconds over `--jobs`.

## Remaining gap (not fixed here)

The planner picks the fewest shards whose planned slowest fits `DB2_TARGET_S` (15 min), so a typical 3-shard plan sits at
the budget and run-to-run noise pushes about 3 runs in 4 over it. Candidate slice, in `tests/tools/det_sweep_plan.py`
and `ci_shard_plan.py`: plan against a target below 15 min (headroom for the noise), and place the longest case first so
a long pole does not share a shard with an even load. The trade is one more runner per full sweep (pool cap
`DB2_MAX_SHARDS` = 6), so it needs the sizing in the PR body per `.claude/rules/ci-workflows.md`. #5882 stays open until
a full sweep after such a change meets both numbers.
