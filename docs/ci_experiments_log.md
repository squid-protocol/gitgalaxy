# CI experiments log

What has been tried to make CI faster or cheaper, what was measured, and what was decided. **Read this before
proposing a CI change**, and add an entry when you try one. `docs/ci.md` describes how the pipeline works *now*; this
page records *why*, including the ideas that were measured and dropped, so nobody re-litigates a dead end from scratch.

## How to read and add an entry

Every entry has: the **hypothesis**, the **change** (or "not built"), the **measurement** with its method and sample,
the **verdict** (`shipped`, `open PR`, `rejected`, `measured, not built`, `deferred`), and a **follow-up** when the
after-number is still owed. Quote numbers with their sample and date. A claim without a measurement is a hypothesis,
not an entry. Newest first within each section.

## What limits CI (read this first)

- **The bottleneck is the runner pool, not compute.** The repo is public: about 20 concurrent jobs, all
  `ubuntu-latest`, 0 self-hosted runners (2026-10-25). The five required checks (`det`, `full-suite`, `ground-truth`,
  `mypy-audit`, `ruff-audit`) need ~5–7 min of compute but take 16–30 min wall, almost all of it queue wait
  (docs/ci.md, #5543 tables).
- **Count slot-minutes, not runner requests.** A job waiting in the queue does not hold a slot; only running time
  does. So the cost of a job to everyone else is its run time. Cutting a 0.2-min job saves ~0.2 slot-minutes no
  matter how long it queued. (This corrected a wrong estimate during the 2026-10-25 review: see "Combine the five
  accuracy audits" below.)
- **A non-required check's wall time never delays a merge.** Auto-merge waits on the five required checks only.
  For advisory workflows, only their slot-minutes matter.
- **Serial jobs matter for required checks.** Each `needs:` hop on a required check is one more queue wait on its
  critical path (#5543's warm-job / plan-fold measurements).

### Measurement methods that worked

| Question | Method |
|---|---|
| What a workflow costs per PR | `gh api repos/OWNER/REPO/actions/runs/RUN/jobs`; sum `completed_at - started_at` per job (slot-minutes). Queue wait is `started_at - created_at`, reported separately. |
| Whether a check ever catches anything | `gh api .../actions/workflows/ID/runs?event=pull_request&created=>=DATE&status=failure` `total_count`, per status. Success counts include draft runs whose jobs skipped. |
| Which tests a shard run duplicates | Temporary `--junitxml` + `upload-artifact` on both workflows, one branch dispatch each on the same commit, then compare per-test outcomes (passed in both / ran only in one). Drop the measurement commit afterwards. |
| What a planner would do | Replay it over the last N merged PRs: `gh pr list --state merged --json number,files,mergeCommit`, and `git diff --name-status SHA^ SHA` when the file status matters. |
| Queue depth | The `N PR jobs waiting for a runner` line that `tests/tools/ci_layout.py` prints in mainframe-ground-truth's `plan` job log. |
| Cache pressure | `gh api repos/OWNER/REPO/actions/cache/usage`, and the oldest entry's `last_accessed_at` (eviction age). |

---

## 2026-10-25 review (one session: issues #6664, #6670, #6672, #6675)

Starting point, measured from ~700 job records of PR runs on 2026-10-25: **58% of PR slot-minutes (990 of 1,712) went
to checks that are not required.** Median queue wait 2–13 min per job.

### Equivalence E2E shards ran ground-truth's tests again — `open PR, shepherd:merge` #6669 (#6664)
- **Hypothesis:** the 4 shards re-run all of `tests/cobol_mainframe/`, which the required `ground-truth` already runs.
- **Measurement:** junit of one run of each on the same commit (E2E 40225533892, ground-truth 40225536142): of 7,822
  tests the shards ran, **7,126 also passed in ground-truth (1,810 s)**; **696 ran only in the shards (3,177 s)**, in
  46 files. 41 of the 46 read `EQUIVALENCE_E2E`; 5 skip in ground-truth for "no JDK 17" without reading it.
  (A file-text estimate had said 84% duplicate; the measured figure is ~36% of shard test time. Measure, don't grep.)
- **Change:** `tests/tools/equivalence_e2e_select.py` keeps files that read the variable or whose skip reason names
  Docker / GnuCOBOL / the oracle image / a JDK / Maven / a jar: 84 files, all 696 kept, 188 s of duplicates left.
  3 shards instead of 4, split over measured seconds (`tests/equivalence_e2e_durations.json`; `.test_durations`
  weighs these tests ~0 s because ground-truth records them skipped).
- **After (branch dispatch 40228310629 vs 40225533892):** shard slot-minutes **50.9 -> 33.2** (−35%), slowest
  shard 16.0 -> 11.4 min, one fewer runner.

### Equivalence E2E `db2` job on every E2E PR — `open PR, shepherd:merge` #6669 (#6664)
- **Measurement:** one runner, ~21 min median. Failed 10 times, all 2026-10-24 22:18Z–10-25 02:10Z (bring-up and a
  since-fixed corpus fetch); **0 failures in its last 58 PR runs**. The required `det` already re-proves Db2 det ports.
- **Change:** the planner runs `db2` on a PR only when a changed file is an input of the five Db2 files (their `ast`
  import closure, the cases they name, shared harness data, non-Python files under `gitgalaxy/`, the job's files).
  Main Watch now watches Equivalence E2E.
- **Replay (80 merged PRs):** `db2` runs on **21 instead of 45**, about 500 slot-minutes per 80 PRs.
- **Not done:** splitting `db2` into more shards. E2E is advisory, so its wall time does not matter; extra shards
  add slot-minutes (Db2 start ~1–1.5 min each).

### Four advisory checks that never failed on a PR — `shipped` #6671 (#6670)
- **Measurement (7 days to 2026-10-25, PR runs success / failure):** Fact Cross-check 702 / 0, unicode-gauntlet
  458 / 0, Estate Crucible 280 / 0, Crucible Path Independence 275 / 0. Job time ~3.4, 3, 0.5, 5.2 min.
- **Change:** their jobs skip on `pull_request`; they run from post-merge dispatch and nightly. The PR trigger and
  its `paths` stay (they are the dispatch's relevance filter and are proven by test_engine_reach_workflows /
  workflow_inputs). The three ratchets are still met before every push by `pr_gates.py --ratchets` / `--fast`.
- **Owner decision:** the security scans (CodeQL, Muninn, the Zero-Trust pre-gate) stay on every PR, though CodeQL
  was 0 / 622.
- **Follow-up:** confirm no `ci-red-main` issue from these four in the first week, or that any was caught within a
  cadence window.

### Ports Compile clean-install check on every PR — `open PR, shepherd:merge` #6673 (#6672)
- **Measurement:** ~3.1 of the job's ~7.9 min (median of 60 PR runs, 39%). **0 failures in ~420 runs** since it
  landed (2026-10-22); all 7 Ports Compile failures in that window were in a different step. Its post-publish twin
  runs only after a release is on PyPI, so it is not a per-merge backstop.
- **Change:** `tests/tools/assess_install_plan.py` runs it on a PR only for packaging changes, the assess command,
  a file added / removed / renamed under `gitgalaxy/`, or a modified file a `package-data` glob ships.
- **Replay (80 merged PRs):** 4 of the 31 that ran Ports Compile (3 added modules, 1 `pyproject.toml`); ~84
  slot-minutes per 80 PRs. A first draft also fired on `language_addition_costs.jsonl` and `.md` edits (6 more
  PRs); tightening to shipped data removed them.

### Actions cache over the 10 GB limit — `open PR, shepherd:merge` #6676 (#6675)
- **Measurement:** **10.69 GB / 127 entries, oldest last read 10.6 h earlier** (2026-10-25). Past 10 GB GitHub
  evicts least-recently-used, so main's caches lived ~half a day. The nightly prune (#4847) took 10.20 -> 5.96 GB
  planned; PRs refilled it within ~12 h.
- **Cause:** 20 combined `actions/cache` steps in 7 PR workflows saved under the PR's own ref, which no other PR
  reads: scip-java 2.18 GB (graph-accuracy never ran on main, so no shared copy existed and every PR started cold),
  9 PR copies of db2-odbc-cli, go / cargo / m2 / image copies.
- **Change:** restore + main-only save for each; setup-go cache off on a PR; graph-accuracy gets a nightly to seed
  its caches; `test_cache_keys.py` fails on any combined cache step or PR-reachable save in a PR workflow.
- **Follow-up (owed):** a day after merge, `actions/cache/usage` and the oldest entry's age. Expect well past
  10.6 h; if it is still under a day, look at the setup-python pip caches (2.8 GB for 3.12 alone, 6 entries).

### Combine the five engine accuracy audits — `rejected`
- **Hypothesis (wrong):** an engine PR starts up to 10 runners for tree-sitter / tri-comparison / call-graph /
  graph-accuracy / detection; one workflow with one plan would save 6–8 of them.
- **Measurement (15 PR runs each):** each `plan` 0.2 min; detection and tri-comparison audits with nothing to do
  0.1 min; tree-sitter 0.7; real work only in call-graph (3.5) and graph-accuracy (10.3, already one job by design,
  #5501). The plan + no-op jobs total **~1.5 slot-minutes per engine PR**.
- **Verdict:** not worth renaming five workflows that CLAUDE.md, the planner, its tests, Main Watch and the
  post-merge dispatch refer to. The runner-request count was the wrong metric (see "What limits CI").

### Merge ruff + mypy into one required job; fold the pre-gate into Small Audits — `rejected`
- ruff + mypy: ~0.5 slot-minutes per PR saved; needs the ruleset's required-check names changed by the owner.
- Pre-gate fold: the owner asked to leave the security checks as they are.

### DOOM-rosetta 4 shards -> 2 — `rejected`
- 4 shards x ~3.8 min; halving the count moves the same work onto fewer runners and saves only ~1 min of setup per
  run. Fewer runner requests, not fewer slot-minutes.

### More shard-count variants to "fit open slots" — `rejected`
- Slots are not shaped by duration: each runner takes one whole job, roughly first come, first served. The shard
  count is fixed when `plan` runs, minutes before the shards start. More shards add per-shard setup (smoke parts
  model ~300 s, Db2 ~1–1.5 min) and, when busy, more chances to wait at the back of the queue. The adaptive
  calm / busy layouts that exist (`ci_layout.py`, `ci_shard_plan.py` `pool_cap`, `suite_shard_plan.py`,
  `crucible_shard_plan.py`) already cover the useful part; #5543 measured that the layout choice barely moves a
  busy run's wall.

### Cancel advisory runs when a required check fails — `measured, not built`
- **Measurement (failed first-attempt required runs since 2026-10-22, 133 heads):** advisory work still to run after
  the failure **369 job-minutes total, mean 2.8 min per failed head**, 16 heads over 5 min: ~105 slot-minutes a day,
  about **2% of PR load**. Every PR workflow already cancels in progress on a new push, which is why it is small.
- **Cost if built:** a cancelled advisory run stops reporting its own failures, which agents use to fix several
  problems in one push.

### Advisory checks yield when the queue is deep — `measured, not built`
- **Measurement (queue depth from 47 ground-truth `plan` logs, 2026-10-25):** median **13** waiting PR jobs; > 8 on
  29 of 47, > 15 on 21, > 20 on 17, > 30 on 7, > 40 on 2. Hourly medians 5–34.
- **Why not built:** a threshold of 8 would skip advisory checks on most PRs, including Equivalence E2E and CICS
  Crucible, which do catch bugs. The post-merge dispatch fires only when nothing is queued, so a skipped PR run would
  usually be covered only by the nightly. If revisited, start at > 30 (~15% of runs).

### Deferred, bigger changes
- **Batched merge queue** (native GitHub merge queue with grouping, or batching in the shepherd): the largest
  standard lever for a fleet of agent PRs. Measure first how many PRs sit approved and waiting at once.
- **More runner supply** (ephemeral self-hosted on the box, autoscaled cloud runners, larger paid runners): the
  limit every measurement points to. Self-hosted on a public repo must never run fork-PR code.
- **Test-result caching** (reuse a pass when a test's import closure and data hash equal a passing main run's): the
  ground-truth scans cache (#5616) is the existing instance. Needs exact input hashing including data files.
- **Prebuilt CI image** (toolchains baked into one image): setup measured at only 0.5–1.5 min per job; jobs that run
  Docker (GnuCOBOL oracle, Db2) would need the socket inside the container. Revisit if #6676 does not settle cache
  thrash.

---

## 2026-10-28 timeout-cap survey (#5156)

Question: which fixed `timeout-minutes` caps sit close to the measured wall time (the #5152 class)? Method: for every
non-shepherd workflow, the longest successful job over its 4 most recent completed runs (any branch), against the cap in
the YAML. Sharded jobs are planned (#5919) and were not hand-capped; the ones listed are the fixed caps.

| Job | Cap | Measured max | Ratio |
|---|---|---|---|
| evidence-refresh `db2 records` | 20 | 10.2 | 0.51 |
| graph-accuracy-audit | 25 | 12.5 | 0.50 |
| mainframe-ground-truth parts (cap 35, #5137) | 35 | 7.7 | 0.22 |
| smoke-test `full-suite` parts (planned) | planned | 6.3 | n/a |
| `plan` / gate jobs (cap 5) | 5 | 0.1-0.9 | <= 0.18 |
| publish.yml, os-smoke-grid, mirror-tag-sync, generated-docs | 10-15 | 1.1-1.8 | <= 0.12 |
| referee-panel | 240 | 21.1 | 0.09 |
| blocker-baseline | 60 | 7.9 | 0.13 |

Result: no fixed cap is above 0.51 of its measured wall time, so no re-cap and no new shard. Caps far above the
measurement (referee-panel 240, blocker-baseline 60, evidence-refresh `refresh` 60) are slack, not a risk: left alone
(a hang costs a runner for the cap; lowering them is a separate speed change). Dropped: re-capping at 1.5x measured,
since it would only tighten slack jobs. Sample is 4 runs per workflow: re-run the survey if a leg is cancelled at its cap.

---

## Earlier work (summaries; details in docs/ci.md)

| When | Issue | What | Measured result |
|---|---|---|---|
| 2026-10-25 | #5543 | ground-truth layouts: warm job, 4 parts calm / 2 busy, `plan` / aggregate folds | calm cache hit 7.5 min wall / 10.9 slot-min; busy runs queue-bound (13–30 min of queue); folding `plan` or the aggregate measured and not done |
| 2026-10-22 | #5133 | full-suite parts balanced by `least_duration`, wall-calibrated durations | part 3 21.4 -> 4.3–5.9 min; balance after calibration still to be measured |
| 2026-10-18 | #5264 | ground-truth split into parts | one 14–16.5 min job -> two of ~11 min |
| 2026-10-15 | #5166 | ReDoS sweeps off PRs that cannot move them; per-test time ratchet | ~18 of tests/extraction's 19 min skipped on non-input PRs |
| 2026-10-14 | #5134 | no branch update just because a PR is behind | superseded-SHA runs were 27% of CI minutes |
| 2026-10 | #5136 | post-merge dispatch cadence (3 h, only when idle) | Full Suite Gate dispatched per SHA had taken 15.6% of all CI minutes |
| 2026-10 | #5132 | fewer PR jobs: pre-gate as one job; Muninn / CodeQL / golden-crucible path filters; Muninn sparse checkout | Muninn step 7m28s -> ~56 s |
| 2026-10 | #5104 | draft PRs start only the cheap audits | — |
| 2026-10 | #4935 / #4964 | tested-tree: skip a main push run when the PR tested the same tree | — |
| 2026-10 | #4518 | Full Suite Gate off the PR trigger (7-leg matrix on every PR starved the queue) | — |
| 2026-10-12 | #4847 | cache prune; hash-only pip keys | 10.6 GB / 208 caches -> pruned nightly |
