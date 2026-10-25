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

## Headroom slice (landed, awaiting a full sweep)

`ci_shard_plan.shards_for` takes a `headroom`; the Db2 shards pass `det_sweep_plan.DB2_HEADROOM` = 0.8, so they plan to
12 min instead of 15. `shard_seconds` also floors a shard at its longest case (the 432 s `cbsa-bankdata` is not split
across `--jobs`); `timeout_minutes` and the `db2_timeout` use it too. Longest-first inside a shard was already
#5947 (`det_port.py run`) and across shards `proof_sweep.split_cases`.

Replay on the committed durations (81 Db2 cases, `DB2_SETUP_S` 420, `--jobs 4`):

| Plan | Db2 shards | Planned slowest shard | Planned shard work (s) |
|---|---|---|---|
| headroom 1.0 (before) | 4 | 858 s | 1738 / 1753 / 1748 / 1750 |
| headroom 0.8 (now) | 6 (the cap) | 852 s | 1167 / 1160 / 1167 / 1166 / 1166 / 1163 |

The 0.8 target (720 s) is not reachable inside the 6-runner cap, so the plan takes the cap. Cost: two more Db2 runners
per full sweep, each paying the Db2 start. Still open: re-measure on the next full sweep (both numbers), and whether
`DB2_MAX_SHARDS` may rise (6 + 6 + plan + det = 14 of the 20-job pool, #5135). #5882 stays open until that sweep meets
the 15 min and 1.3x numbers.

## Recording slice (2026-10-25)

Db2 seconds were written only by Evidence Refresh's nightly merge (`det-db2-durations-`). A manual full sweep
(`workflow_dispatch` on main, `db2_cases: all`) also proves every Db2 case, so the `det` job now restores that cache,
extends it with the Db2 aggregate (`--update-durations --durations durations-db2/...`) and saves it. Pull requests and
partial case lists never write it. The startup ask (create only the databases a shard uses) was already on main: the pool
is `min(4, ceil(cases / shards))` databases per shard, restored from the Db2 snapshot cache. Re-measure on the next full
sweep on main.

## Re-measure with the committed tool (2026-10-25)

The hand calls above are now `tests/tools/det_sweep_measure.py db2` (offline-tested maths in
`test_det_sweep_measure.py`). It reads each run's db2 jobs (`db2 I/N`, start to completion; only successful jobs give
shard times), groups runs by planned db2 job count, and counts a job as a timeout only when its annotation holds "exceeded
the maximum execution time" (a cancelled superseded push is not one). Reproduce:

    python tests/tools/det_sweep_measure.py db2 --since 2026-10-18 --cut 2026-10-25T03:47:00Z   # headroom (#6567) merged 03:46Z
    python tests/tools/det_sweep_measure.py db2 --since 2026-10-18 --event workflow_dispatch    # manual full sweeps

Result (pull_request runs from 2026-10-18; the API window is the newest ~1000 runs):

| Side | Db2 jobs | Complete runs | Slowest >= 15 min | Median / max slowest | Ratio > 1.3 | Timeouts |
|---|---|---|---|---|---|---|
| before the cut | 3 | 62 | 48 | 15.9 / 23.9 min | 17 (median 1.18) | 0 |
| before the cut | 5 | 29 | 1 | 12.2 / 22.9 min | 14 (median 1.30) | 0 |
| after the cut | 3 | 2 | 1 | 15.2 / 15.8 min | 0 (median 1.23) | 0 |

Single-job (narrow) plans are 5-7 min in every window and not an acceptance case.

- **Timeouts:** none in any window (the 2 earlier failures are the non-timeout "Download the plan's durations" step).
  Met.
- **Every Db2 case measured:** `det_sweep_plan.db2_names({"db2_cases": "all"})` gives 81 cases, all 81 have an entry in
  `det_sweep_durations.json`. Met.
- **Shards under 15 min and within 1.3x:** not yet decidable. Only 2 post-headroom runs had a multi-shard plan, both 3
  jobs (narrow-ish case lists, not the 6-shard full plan); neither is a `db2_cases: all` sweep, and no manual full sweep
  (`workflow_dispatch`) or `push` run has any db2 job. The full-sweep numbers still need one run of the main workflow with
  `db2_cases: all`; then rerun the commands above. #5882 stays open until that run meets both limits.

## Full sweeps on main (2026-10-25)

Two manual `workflow_dispatch` runs on main (`db2_cases: all`, 81 Db2 cases, 6 Db2 shards, headroom 0.8). Job minutes are
a db2 job's `started_at` to `completed_at` (what `det_sweep_measure.py db2` reports); sweep seconds are the
`proof_sweep.py` step alone, read from each job log (`echo "$start"` to `sweep: ratchet left to the aggregate`).

| Run | Snapshot cache | Job minutes per shard (1..6) | Slowest | Slowest / fastest | Sweep seconds (1..6) | Sweep ratio |
|---|---|---|---|---|---|---|
| 40171341678 | cold (all 6 missed `db2-snapshot-...-pool4`) | 16.0 / 10.5 / 10.6 / 8.9 / 11.6 / 10.0 | 16.0 min | 1.80 | 512 / 413 / 447 / 382 / 418 / 428 | 1.34 |
| 40174285397 | warm (all 6 restored it) | 9.7 / 8.9 / 8.4 / 9.65 / 8.15 / 10.35 | 10.35 min | 1.27 | 434 / 383 / 317 / 422 / 314 / 422 | 1.38 |

- **Why run 1 missed:** the pool-size change (#6545) changed the snapshot key, so no shard had a snapshot. Every shard
  paid the full Db2 create, and shard 1 also spent 3.4 min saving the cache after its sweep (07:41:33 to 07:44:52);
  without that tail its job is 12.6 min. The key is saved on main now, so a cold start is a one-off per key change.
- **Warm run 2:** every shard is under 15 min (slowest 10.35) and the job-minute ratio is 1.27, so both acceptance
  numbers hold on job minutes. Measured on the sweep step alone the spread is 1.38 (314 s to 434 s): case seconds still
  move run to run, as above.
- **Timeouts:** none in either run. **Measured durations:** the `det` job saved `det-db2-durations-40171341678` and
  `-40174285397`, so every Db2 case has a fresh entry.
- Reproduce: `python tests/tools/det_sweep_measure.py db2 --since 2026-10-18 --event workflow_dispatch`.
- Verdict: 15 min met in both warm and cold-minus-save; 1.3x met on job minutes in the one warm run, not on sweep
  seconds alone. If a later warm full sweep goes over 1.3x on job minutes, the next fix is `split_cases` balance (the
  432 s `cbsa-bankdata` case pins one shard's floor), not a higher `DB2_MAX_SHARDS`.
