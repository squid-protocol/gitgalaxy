---
description: "How to measure a performance change to the scan hot path without fooling yourself —"
---
# Speed-testing the engine

How to measure a performance change to the scan hot path without fooling yourself —
and, just as important, without fooling yourself in the *other* direction by dismissing
a real gain because it happens to be invisible on the machine you ran it on.

## The tools

- **Per-phase telemetry**: run any scan with `--file-speed --splicing-speed`. This prints
  the macro-phase breakdown (`5_Optical_Detector`, `5.5_Security_Lens`, …) and the per-regex
  and per-file tails. These totals are **cumulative worker CPU** — summed across every worker
  process — so they exceed, and are independent of, the parallel wall clock.
- **A/B harness**: `tests/tools/phase_ab.py` runs one repo across two-or-more engine checkouts
  in alternating rounds and reports each phase total per engine with the delta vs baseline,
  an A-vs-A control, and an artifact-identity diff. See the `perf-ab` skill for the full
  playbook.

## Measuring honestly

1. `export GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER` — otherwise a license delay skews timings.
2. Drive the engine by importing `gitgalaxy.galaxyscope.main()` over `PYTHONPATH`, never the
   installed console script, which runs whatever is on `PATH`.
3. **Alternate** the engines every round, never "all A then all B" — background drift aliases
   onto a blocked comparison.
4. Run an **A-vs-A control**: re-run the baseline under a second label. Its delta is your noise
   floor. A real change must clear it *and* keep a consistent sign across rounds.
5. Prove "changes nothing" on the **deterministic surface** — `audit.json` (ignoring the
   `Analysis ISO Timestamp` / `Total Scan Duration` keys) and `sarif.json`. The `master.db`
   call lists carry hash-seed nondeterminism and are not a valid diff surface.

## It is not just one machine

The scan parallelizes across cores, one worker per file. On a fast box with many cores, the
**wall clock is dominated by that parallelism**, and single-threaded, CPU-bound work inside a
worker is largely hidden. A change that measurably reduces per-worker CPU can therefore look
like *nothing* on the wall clock of a high-core dev machine — while mattering on the hosts the
engine actually has to run well on:

- **Fewer cores** (CI runners, laptops, small containers): with less parallelism, per-worker
  CPU sits much closer to the wall, so the same CPU saving translates more directly to wall time.
- **Slower clocks / constrained power**: the absolute CPU time is larger to begin with, so a
  fixed percentage reduction is a larger absolute win.

The practical rules that follow:

- **Judge per-worker CPU, not only wall on your box.** cProfile `tottime` on the changed
  function, or the `--file-speed` phase totals (cumulative worker CPU), are the signal that
  survives across hardware. Report them alongside wall, and say which machine the wall figure
  came from. Caveat: cProfile charges C-level regex time to the Python caller, so use it to
  locate a hotspot, then size it with `tests/tools/phase_ab.py` phase totals.
- **Don't dismiss a CPU reduction just because it is sub-noise on the wall here.** If cProfile
  shows the work genuinely shrank and the output is byte-identical, it is a real, portable
  improvement — frame it as such, scoped to where it helps.
- **Don't over-claim the mirror image, either.** A wall win on a fast, many-core box can shrink
  on a host that is I/O- or memory-bound rather than CPU-bound. State the conditions of the
  measurement so the number can be trusted for what it is.

Worked example: the #3174 Mode-B cleanup cut `_slice_by_braces` per-match CPU by ~11% in
cProfile with byte-identical output, which is ~0.2% of Optical_Detector wall on the many-core
dev box — below that box's noise floor, but a proportionally larger win on a core-constrained
host. The change was shipped and framed on exactly those terms, not sold as a headline wall
number.

## Combined-alternation scan for `coding_analysis` (#3073): measured, stays deferred

A reassessment datapoint (2026-10-17, after #3072 and #3182 closed), not a full A/B. Scan of
`gitgalaxy/standards` (113 files, mostly Python, `--splicing-speed`, min-of-1, quiet box): the
cumulative regex table is led by one rule, `python::Cartography_Mode_C_Indentation` at 0.894s;
the next fourteen rules sum to about 0.77s (largest: `state_mutation` 0.119s, `fragile_debt` 0.106s), and
none of them exceeds 0.12s. The fleet data in the #3073 comment says the same at scale
(`B_Braces` 53% of rule CPU, top 5 of 662 rules 50%). The remaining cost is a few hot
single rules, which a merged alternation does not touch, so the issue's parity hazards (100-group
limit, scoped flags, per-rule Match objects, alternation-order span drift) still buy too little.
Reopen only with a fleet-scale `phase_ab.py` run showing the many-small-rules residual is large.

## Cold-storage prefetch A/B and warm no-regression (#3189)

`phase_ab.py --evict` drops the target tree from the page cache (`posix_fadvise(DONTNEED)`, no root) before every
scan, and `--env LEG:KEY=VAL` sets an environment variable for one leg only, so one checkout can be both legs:
`--engine off=$PWD --engine on=$PWD --env off:GITGALAXY_PREFETCH=0 --env on:GITGALAXY_PREFETCH=1`. Eviction is best
effort (dirty or mapped pages stay), and the A-vs-A `--control` leg runs under the baseline's env.

Measured 2026-10-18, zero-dependency scan, shared box under other load, 3 rounds alternating, `--evict --control`.
Target `all_language_repo` (8,071 files) on `/srv/storage_16tb` (sda, rotational):

| leg | wall | 2_Disk_IO |
|---|---|---|
| off (`GITGALAXY_PREFETCH=0`) | 49.43 s | 3.82 s |
| off#ctl (A-vs-A) | 45.45 s | 3.22 s |
| on (`GITGALAXY_PREFETCH=1`) | 45.19 s | 0.77 s |

- `2_Disk_IO` falls about 3.0 s (-80%; every "on" round 0.58-0.89 s, every "off" round 3.5-4.4 s). The wall delta
  is inside the noise floor (control -8.1%, one off round was 58.9 s under load): do not read it as a wall win.
- `*_galaxy_audit.json` (volatile keys stripped) and `*_galaxy_sarif.json` are IDENTICAL, off vs on and off vs control.
- Warm and small (`gitgalaxy/standards`, 113 files, no `--evict`, 5 rounds): wall 1.62 s off, 1.56 s control, 1.59 s on;
  `2_Disk_IO` 0.00 s on every leg; artifacts IDENTICAL. No regression.
- Limits: this 3 s of disk time is far from illumos's 425 s (a mega-repo, not available here), and an evicted page cache
  is warmer than a spun-down HDD. It proves the prefetch removes the Phase-2 read wait and changes nothing in the
  output; the mega-repo figure still needs a real cold run.

### The #3073 parity precondition is now met (harness only, engine unchanged)

`tests/tools/combined_alternation_parity.py` builds the issue's one prototype shape, a first-pass
candidate finder: one combined regex of every rule's required literals, swept once per segment,
yielding the candidate rules. It scans with a zero-width lookahead over literals reduced to those
with no other literal as a substring, so a leftmost alternative cannot consume the text a second
one needs; case-insensitive gates use a second regex over `fold_haystack(text)`. Contract: every
rule whose `finditer` matches is a candidate. Run over language-crucible (55 languages, 2,995
files) and keyword-rosetta (raw and code-stream surfaces): zero missed candidates. It is a
superset of today's per-rule gate (it widens, never narrows), so it only pays if a fleet-scale
`phase_ab.py` run shows the many-small-rules residual is large; the issue stays deferred.

### The #3073 fleet-shaped measurement: the combined finder costs more than the gate it replaces

`combined_alternation_parity.py --time --corpus crucible` times three stages over the code streams of
language-crucible (55 languages, one pass, quiet box, min-of-1): the per-rule literal gate that
`detector.py` runs today, the combined candidate finder, and the real `finditer` sweeps of the
gate-accepted rules. Totals: gate 1.12s, finder 9.03s, sweeps 36.94s. The sweeps are the work any
scheme still has to do to confirm a candidate; only the gate stage is replaceable, and the finder
is about 8x slower than it (a lookahead alternation attempts every literal at every position; the
gate is one C-speed substring probe per literal). The residual (sweeps outside each language's five
costliest rules) is 17.17s, 45% of gate plus sweep, but a candidate finder cannot remove it:
those rules do match, and each match still needs its real Match object. The hot rules dominate
single languages (CSS: 7.5s of 7.6s in its top five). Verdict: #3073 stays deferred; the cost lives in the
rules, not in the gating, and the lever remains per-rule work (#3072, #3182). Rerun the command to reproduce.

### The #3073 re-measurement on main 35480422a (2026-10-24): same verdict

Two churn runs re-ran `combined_alternation_parity.py --time` (the #6125 harness) on main 35480422a:
the combined candidate finder took 16.33s against 1.73s for the per-rule literal gate (about 9.4x
slower), and the residual `finditer` sweeps were unchanged. The finder is slower than the stage it
would replace on every measurement so far (8x, 9.4x), and the sweeps it cannot remove dominate. No
engine change follows. #3073 stays deferred; whether to close it as not planned is the owner's call,
and the lever remains per-rule work (#3072, #3182). Reopen only with a fleet-scale `phase_ab.py` run
that shows the many-small-rules residual matters.
