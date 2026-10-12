---
name: box-capacity
description: Keep a multi-agent fleet inside what the box can take, and keep agents off each other's toes. Use BEFORE launching an agent or any heavy run (proof sweep, pr_gates, full suite, Docker e2e, det_port check) while other agents run, when the box feels slow or cores are pegged, when agents may touch the same files or shared resources (Db2 container, crucible pins, golden masters), or when a night-shift tick decides whether to launch. Covers the box_status.py verdict (GREEN / YELLOW / RED), admission rules, what counts as heavy, overload response, the collision check between in-flight branches, and the shared singletons. Referenced by parallel-pr-agents and the night-shift skill.
---

# Box capacity: admission control and collision avoidance for agent fleets

Agents share one box (cores, memory, the Docker daemon, one Db2 container, the crucible pin checkouts, the GitHub API
budget). Counting agents is not enough: on 2026-10-11 the 15-minute load reached 13.5 on 12 cores with "only" a couple of
agents, because the orchestrator's own gate runs, unwrapped pytest runs and Docker proofs ran beside theirs. Overload is
not just slow: load-induced regex timeouts faked 2,911 golden diffs (#4247), and proofs time out. The orchestrator decides
from a measurement, every time.

## 1. Measure: `tests/tools/box/box_status.py`

```bash
python tests/tools/box/box_status.py           # table
python tests/tools/box/box_status.py --json    # for a script or a night-shift tick
```

It reports cores, load (1/5/15), CPU and memory pressure (Linux PSI "some" avg60: the share of time tasks waited for a core
/ for memory), memory available, swap in use, who holds each `heavy-run.sh` slot and the golden lock (PID, worktree,
command), the busiest worktrees by cores in use, disk I/O pressure with the busiest disk readers/writers and the processes
blocked on disk, probable strays, and the running containers, with one verdict (`decide()`, pure, tested in
tests/tools/test_box_status.py):

| Verdict | Means | Do |
|---|---|---|
| GREEN | headroom | launch; heavy work only into a free slot (`free_slots`) |
| YELLOW | load >= 70% of cores, CPU pressure >= 15%, disk I/O pressure >= 50%, memory pressure >= 5%, memory available < 20%, or all slots held | light work only: a read-only scout, a narrow `pytest -k`, review; no proof, sweep, gate, full suite, Docker run |
| RED | load >= cores, CPU pressure >= 40%, memory pressure >= 20%, or memory available < 10% | launch nothing; see 4 |

Swap merely in use is shown but not judged alone: it can be old pages pushed out by a spike long gone (4 GB of swap with
22 GB available and 0% memory pressure is GREEN). Paging NOW shows as memory pressure.

**Load is not CPU (#4930).** Linux counts tasks blocked on disk (D state) in the load average. YELLOW from load with CPU
pressure near 0 means the disk is the bottleneck: the reason then says "mostly tasks waiting on disk: <culprit>" and the
`disk:` lines name the reader. On 2026-10-11 a stray `find /` (aliased to `bfs`) held the box YELLOW for 40 minutes with
nothing in "busiest". Load with neither CPU nor I/O pressure behind it (tasks stuck on a dead mount) is reported and not
judged. A whole-filesystem scan (`find`/`bfs`/`fd`/`du`/`rg`/`grep` over `/`, `/home`, `/srv`, `/srv/storage_16tb`, `$HOME`)
alive 15+ minutes is listed as `STRAY?` with its pid.

## 2. Admission (before every launch and every heavy run of your own)

- Run `box_status.py`. RED: wait (re-check in ~10 min) or queue. YELLOW: only light agents/commands.
- **Heavy agents <= free slots.** A worker that will prove, sweep, gate or run Docker is heavy; count the slots the
  orchestrator's own runs hold. Slots are `GG_HEAVY_SLOTS` (default nproc/4: 3 on a 12-core box), fixed before a fleet
  starts and never changed mid-run (parallel-pr-agents: lock tiers).
- **Light agents** (Haiku scouts reading files and the GitHub API, a reviewer) can run beside heavy ones on GREEN or YELLOW.
- **One Docker-heavy job at a time per kind:** the Db2 container is one shared singleton (one Db2 proof run at a time);
  GnuCOBOL/javac e2e runs go through `heavy-run.sh`.
- Usage limits are separate (parallel-pr-agents: concurrency cap): box headroom never justifies exceeding the agent cap.

## 3. What counts as heavy (wrap it in `heavy-run.sh`, orchestrator included)

Heavy: `pr_gates.py --fast` / `--ratchets`, the full or a large pytest run (hundreds of tests or `-n`), `det_port.py run` /
`check`, `proof_sweep.py`, `evidence.py prove`, `cics_census.py survey`, `crucible_check.py` (golden: `golden-lock.sh`, not
`heavy-run.sh`), any `EQUIVALENCE_E2E=1` run, a galaxyscope scan of a corpus.
Light: `pytest file -k name` on a few tests, `ruff`, `git`, `gh api`, reading files, `register.py render`.
Put the wrapping in every worker brief (the `gitgalaxy-pr-worker` agent already says so) and do it yourself.

**Parallel tools size themselves from the slot.** `heavy-run.sh` exports `GG_JOB_CORES` = nproc / the heavy slots held
when the job starts (alone: every core; two jobs: half each). `pr_gates`' unicode gauntlet uses it for `--jobs`; before
#4882 it took every core in every slot, so two gates at once ran load 52-86 on 12 cores. A new parallel step (an `-n`
pytest, a `--jobs` sweep) reads `GG_JOB_CORES` the same way, never `os.cpu_count()` alone.

## 4. Overload response

- RED once: launch nothing new; finish or queue your own heavy runs.
- RED on two checks ~10 minutes apart: ask the NEWEST heavy worker (SendMessage) to finish its current step, push a WIP
  commit, update its handoff and pause until told to continue. Never kill a worker mid-proof (its queued flock'd jobs
  keep running; parallel-pr-agents: stop-cleanup with `kill-by-cwd.sh --dry-run` first if you must stop one).
- Find the hog in the "busiest" list: a worktree burning cores with no agent behind it is an orphan (a stopped agent's
  pr_gates or sweep): `kill-by-cwd.sh <worktree> --dry-run`, review, then kill.
- YELLOW/RED with a `STRAY?` line or a disk culprit nobody owns: it is almost always a command an agent left behind
  when its tool call timed out (the harness moves it to the background, where it keeps running). Check the pid's parent
  and cwd; if no agent or person owns it, `kill <pid>`. Never start a whole-filesystem scan yourself: search the project
  directory, or `git ls-files` / `git grep`.
- Not ours: the daily `chkrootkit` (root) walks /tmp with a shell per file and can run for hours when /tmp is large; it
  costs ~0.1 core. Cleaning old scratch under /tmp shortens it.
- Idle singletons hold memory: a Db2 container up for days with no Db2 run pending can be stopped
  (`docker stop gitgalaxy-db2`; the harness starts it again) -- only when no agent's Db2 proof is queued.

## 5. Collisions between agents (check before launch)

- **Files.** For each in-flight branch: `git diff --name-only origin/main...origin/<branch>`. A new task that will edit the
  same source files waits, or is told the exact seams (a new function / block / test at a distinct anchor, never a reorder).
  Hot files on this repo: `gitgalaxy/tools/cobol_to_java/det/cics.py`, `det/program.py`, `det/stmt.py`,
  `cobol_to_java_transaction_forge.py`, `cobolrt/Cobol.java`, the spec under `gitgalaxy/standards/cics/`, and the test files
  agents append to (`tests/cobol_mainframe/test_det_translate.py`, `test_equivalence_cics.py`,
  `tests/cics_crucible/test_cics_runtimes.py`): two PRs appending at the same anchor conflict; the second to merge keeps
  both blocks.
- **Generated / ratchet files:** never hand-merge `docs/language_status/oracle_assumptions.md` (`register.py render`),
  golden masters (`golden-lock.sh crucible_check.py --update --yes`), the ruff/mypy baselines (regenerate),
  `tests/equivalence/det_sweep_baseline.json` and the coverage ledger (their tools). Take main's side, regenerate.
- **Shared runtime changes** (`cobolrt/`, `DetCics`, the forge) move every port: one such PR in flight at a time, and its
  `det_port.py check` list goes in the PR.
- **Shared checkouts and scratch:** crucible pin checkouts change only via `sync-pins.sh` (under `golden-lock.sh`); shared
  scratch: each agent writes only its own subdir; never two agents in one worktree; never an agent in another tool's clone.
- **GitHub API:** 5,000 requests/hour for all agents together: no tight polling loops (sleep >= 60 s, `per_page=100`).

## 6. Checklist (orchestrator, per launch)

- [ ] `box_status.py` verdict allows it (heavy: GREEN with a free slot; light: not RED).
- [ ] File overlap with in-flight branches checked; seams named in the brief, or the task queued.
- [ ] Singletons it needs (Db2, golden lock, pins) are free or queued behind their holder.
- [ ] The brief says: heavy commands through `heavy-run.sh`, golden through `golden-lock.sh`, own scratch subdir.
- [ ] My own heavy runs are counted and wrapped too.
