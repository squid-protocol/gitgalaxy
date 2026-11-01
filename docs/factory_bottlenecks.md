# Code factory bottlenecks

What limits how much the agent factory merges, what was tried, what was measured, and what was decided. **Read this
before proposing a change to churn, the shepherd or how work is sliced**, and add an entry when you try one.
`docs/ci_experiments_log.md` does the same for CI alone. The RSI lane's weekly jobs (`churn rsi`) feed this page.

## How to add an entry

Use the CI log's format: hypothesis, change, measurement with its method and sample, verdict (`shipped`, `open PR`,
`rejected`, `measured, not built`, `deferred`), and any follow-up owed. A claim without a measurement is a hypothesis,
not an entry. Newest first. Record what failed as carefully as what worked: a dead end is the most useful entry here.

## Where the factory loses time

Measured 2026-11-01. Re-measure with `churn rsi conflicts`; replace these figures rather than adding to them.

| Limit | Measure | Note |
|---|---|---|
| CI capacity | 20 shared runners, about 95% used on 2026-10-30 | The main limit on most days (`docs/ci_experiments_log.md`) |
| Plan holds | 30 held runs in 7 days: 54 of 75 file-level holds on data files, 12 on code, 7 on tests, 2 on docs | Most data holds are hand-written `case.json` and are real conflicts |
| Repeat fix rounds | #7389: 22 rounds on one blocker | Stopped by `fix_loop_stop` |
| False reds | 22 of 41 `env` fix runs, 10-29 to 10-31, found only cancelled checks | Stopped by #7432, #7465 and promoter-bot #96 |

## Reading the numbers

Each of these misled someone on 2026-11-01.

- **A cancelled run is not lost capacity.** 6,544 of 9,321 shepherd reconcile runs were cancelled, but all 100 sampled
  had no job, so they took no runner. Count runner minutes, not runs.
- **A failed check may not be a failed test.** Read the run's conclusion first. Until #7465 a superseded run's gates
  ended `failure`.
- **"Unknown" means no reading, not a hold.** The 10-29 and 10-31 gaps on the limits chart were nyx offline.
- **A file-level hold count overstates a fix.** 54 data holds sounded like the top target; a replay of the fix removed
  4 of 30 held runs. Replay a change against real history before ranking it.
- **Check the example that prompted the work.** See the approval entry below.

## Entries, newest first

### Attack survivors before excusing them (2026-11-01): shipped (#7474)

- **Hypothesis:** L5 counted a label the same as a kill, and no tool could aim at a det port's survivors, so survivors
  were labelled instead of tested.
- **Change:** `tests/tools/survivor_attack.py` and the `survivor-attack` skill. `det_mutation.py state` now refuses an
  `equivalent` / `unreachable` verdict with no attack on record, or a reason that only says what the tests do.
- **Measurement:** origin/main e444a35ac: 3,966 survivors in 34 programs, all accounted, none open. 141 of the 145 gaps
  open on 2026-10-23 still survive with the same Java line, relabelled on 10-30 with no case file changed. Audit of 24
  random verdicts: 3 killed by a new input on the real oracle, 1 mislabelled, 20 held (range for 3 of 24: about 3-32%).
  Lint refuses 80 of the 3,966 stated reasons. Ranking puts 2 of the 3 kills in the top 10%, measured on the examples it
  was written from, so treat it as an order of work and not a detector.
- **Verdict:** shipped as tooling. L5 still means every survivor accounted for, and the kill rate is published beside it. The 3,966 stated verdicts stand until re-attacked.
- **Follow-up:** re-attack ZECS003, COSGN00C and the 141 relabelled mutants. `strengthen.py --case-gaps` reads only
  `mutation_scores.json`, so batch det cases still have no attack route.

### Keep approval on a merge-only update (2026-11-01): rejected

- **Hypothesis:** PRs that only take main lose approval and re-run CI, as #7441 and #7439 seemed to.
- **Change:** #7464 let approval survive when the PR's own patch was unchanged, including files main also touched.
- **Measurement:** replayed over the 72 recent approval drops: 2 kept, 70 still dropped (52 were real commits, 9 merges
  changed the patch, 7 approved heads were further back than a parent, 1 unreadable head, 1 patch already on main).
  Both #7441 drops were conflict resolutions and #7439's was a real commit, so all three were correct.
- **Verdict:** rejected, closed unmerged. `clean_main_merge` already keeps approval on a clean merge and refuses files
  both sides touched. Allowing those overlaps loosens a safety gate for almost no gain.
- **Follow-up:** the PR found a small gap: a mode change inside a merge, on a file main touched, is not compared.
  Worth a small fix of its own if it ever matters.

### Calm the shepherd's reconcile runs (2026-11-01): shipped (#7463)

- **Hypothesis:** 319 of the 500 most recent cancelled runs were reconcile, so it wastes much of the pool.
- **Change:** a `skipped` completion takes no pass and cannot replace a real pending one.
- **Measurement:** all 9,321 reconcile runs, 10-25 to 11-01. Real passes use about 5.4 runner-hours a day, about 0.2 of
  one slot. Replay of 10-31: cancelled rows 1,399 to 951, passes 260 to 253, wait 58 s to 59 s.
- **Verdict:** shipped as tidiness, not capacity. The hypothesis was wrong: those runs were nearly free.
- **Follow-up:** after merge, confirm skipped completions show as `skipped`.

### Cancelled gates ending as failed (2026-11-01): shipped (#7465)

- **Hypothesis:** gates using `always()` report `failure` when their run is cancelled, which sends workers to fix nothing.
- **Change:** five required gates use `!cancelled()`. A skipped required job reads as green, so this was tested live:
  gates in a cancelled run ended `cancelled`, not `skipped`, and a job timeout still fails its gate.
- **Measurement:** across 108 cancelled PR runs, those five were the only jobs ending `failure`.
- **Verdict:** shipped.
- **Follow-up:** any gate showing `skipped` in a cancelled run means revert at once.

### Repeat fix loops (2026-11-01): shipped (promoter-bot #98)

- **Hypothesis:** merge-only fix rounds on a blocked PR repeat with no progress.
- **Change:** after 2 rounds with the same red checks and no hand-written change, hold the PR and name the blocker.
- **Measurement:** #7389 had 22 rounds; this leaves 2, saving 20 rounds and 236 workflow runs.
- **Verdict:** shipped. Known cost: replayed further back it would also have paused #5805, #5836 and #5838 on 10-21,
  which merged that day, so each would have needed a release.

### Plan holds on data files (2026-11-01): shipped (promoter-bot #97)

- **Hypothesis:** data files cause most holds, and regenerated ones need none.
- **Change:** tool-written files stop holding; a ladder slice waits at launch for a live worker on its estate.
- **Measurement:** replay of 7 days: held runs 30 to 26, data holds 54 to 38.
- **Verdict:** shipped, modest effect. `case.json` and `infeasible_outcomes/` still hold, correctly.
- **Follow-up:** at least 6 remaining ladder holds were slices whose labelled estate was finished, so the worker moved
  into another estate. A line in the ladder brief ("stay in this estate; if nothing is left, report and stop") may fix these.

### Splitting the CICS hot files (2026-10-16 to 11-01): shipped (#5274)

- **Hypothesis:** plan holds are per file, so splitting files many slices edit lets slices run side by side.
- **Change:** family modules and registries across the harness, det translator, C stub and tests. Recipe: the
  `hot-file-split` skill.
- **Measurement:** holds on the hot files fell from about 4.6 a day (10-13 to 10-19) to about 0.85 a day. Part of that
  may come from other changes, and the gate now also waits without spending a plan run.
- **Verdict:** shipped. Worth finishing, but these files were only 11 of 96 held runs by then.
- **Follow-up:** a family hook for the harness's run pipeline was dropped: almost none of its commits would have landed
  in one. The weekly conflict job decides what comes next.
