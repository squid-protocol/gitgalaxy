# Test Time: the Suite Must Not Get Slower (#5166)

* A test whose CI duration exceeds **10 s** fails the full-suite part (`time_ratchet.py check`) unless it carries
  `@pytest.mark.slow(reason="...")` (the reason is required; `tests/conftest.py` refuses an empty one) or is listed in
  `tests/test_time_baseline.json`. Prefer making it faster (fixture scope, one scan instead of many) to marking it.
* A baselined test fails past **2x** its recorded seconds. The baseline only shrinks: `python tests/tools/time_ratchet.py
  update --times .test_durations` (or the junit-free times file a run writes with `GITGALAXY_TEST_TIMES=file`) lowers entries
  and drops those at or under 10 s; it never raises or adds one. Never hand-edit a number up.
* The whole-suite budget (`suite_budget_s`) is gated on the nightly main run (>10% over fails and files one issue) and only
  reported on PRs. When the suite gets faster, `update` lowers it.
* Local check: `python tests/tools/pr_gates.py --ratchets --only-ratchets time` (reads the committed `.test_durations`).
* **A test just under 10 s locally can exceed the ratchet on CI** (runners are 1.2-2x slower): mark it
  `slow(reason=...)` up front (#5179). The "Per-test time ratchet" step lists every offender at once; match that list
  against a sibling PR's actual diff, not its title, since the list may leave files out (#5177).
