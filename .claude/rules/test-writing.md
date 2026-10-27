# Test Time: the Suite Must Not Get Slower (#5166)

* A test whose CI duration exceeds **15 s** (`FAIL_S`; 10-15 s is a warning, owner 2026-10-15) fails the full-suite part
  (`time_ratchet.py check`) unless it carries
  `@pytest.mark.slow(reason="...")` (the reason is required; `tests/conftest.py` refuses an empty one) or is listed in
  `tests/test_time_baseline.json`. Prefer making it faster (fixture scope, one scan instead of many) to marking it.
* A baselined test fails past **2.5x** (`FACTOR`) its recorded seconds. The baseline only shrinks: `python tests/tools/time_ratchet.py
  update --times .test_durations` (or the junit-free times file a run writes with `GITGALAXY_TEST_TIMES=file`) lowers entries
  and drops those at or under 10 s; it never raises or adds one. Never hand-edit a number up.
* The whole-suite budget (`suite_budget_s`) is gated on the nightly main run (>10% over fails and files one issue) and only
  reported on PRs. When the suite gets faster, `update` lowers it.
* Local check: `python tests/tools/pr_gates.py --ratchets --only-ratchets time` (reads the committed `.test_durations`).
* **A test near the limit locally can exceed it on CI** (runners are 1.2-2x slower). Since #5186 an unmarked, unbaselined
  test fails only over 15 s (`FAIL_S`); 10-15 s is a warning. Mark one `slow(reason=...)` up front only if it cannot be
  made faster (#5179). The "Per-test time ratchet" step lists every offender at once; match that list
  against a sibling PR's actual diff, not its title, since the list may leave files out (#5177).
* **A test that runs `java`** passes `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8` and decodes output as UTF-8:
  `test_java_subprocess_utf8.py` scans every `tests/` file and the ground-truth CI job fails otherwise (#5232).
* **`time_ratchet.py check --times .test_durations` skips the source slow-mark read** and false-fails tests whose cost is
  a shared fixture; run it with no `--times` to check the committed file (#5255).
* **`test_the_workflow_reads_nothing_the_planner_skips` scans the whole workflow text, comments included:** a comment
  naming a `tests/tools/` path counts as a ground-truth plan input (#5264).
* **`pytest_split` is not in the selfscan venv:** replay `least_duration` by hand (heaviest first into the lightest
  group) or use the CI venv (#5264).
* **A module-scoped fixture's cost lands on whichever test runs first in a CI split part,** so any consumer of an
  expensive fixture can trip the per-test time ratchet (#5269).
* **A baselined test fails at 2.5x its baseline even when slow-marked:** split it instead of marking it (#5613).
* **A test gated on `GITGALAXY_NIGHTLY` is invisible to push/PR CI,** so the time ratchet first sees it on the scheduled run:
  mark it slow up front (#5994). On a time_ratchet failure read the `--durations` per-phase lines before assuming the test
  is slow (#6204).
