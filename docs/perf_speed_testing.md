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
  came from.
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
