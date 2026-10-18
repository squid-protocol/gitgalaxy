---
description: "Python and test-writing traps that cost fleet workers a round trip: optional dict keys, default-arg binding, float tolerances, ReDoS timing transport, whole-repo scans in tests"
globs: "gitgalaxy/**/*.py,tests/**/*.py"
---
# Python and Test Traps

* **A new optional key in a coverage/reading dict is added only when non-empty.** An always-present empty key breaks
  exact-equality and evidence-report tests (#5100).
* **A default arg binds at definition time.** `def f(path=BASELINE)` ignores a test's monkeypatch of the module
  constant; default to `None` and resolve inside the function (#5169).
* **Tolerance checks compare against the scaled bound.** `total / budget - 1 > 0.10` misjudges the exact boundary in
  floats; write `total > budget * (1 + tol)` (#5169).
* **A child stuck in a regex never flushes `multiprocessing.Queue.put`** (the feeder thread needs the GIL). Send
  batched ReDoS timings through a `Pipe` (#5171).
* **A test that builds `Orchestrator(".")` and calls `execute_pipeline` scans the whole repo** through the ecosystem
  audits. Give it a temp root (#5171).
* **`ruff format` reflows multi-line expressions even beside `# fmt: skip`.** After formatting, re-check any test that
  pins source text (#5173).
* **CodeQL `py/uninitialized-local-variable`:** a local assigned inside one `if` and read under a later separate `if` must be initialised before the first block, even when the guards are identical (#5196).
* **Never regex-scrub verdict words over a rendered report:** it mangles identifiers like `ported_unproven`; use word
  boundaries that exclude `_` (#5231).
* **A guard wrapping `socket.connect` also catches stdlib loopback plumbing** (Windows `socketpair` emulation): test
  socket guards on a Windows leg (#5253).
* **CI helper scripts the workflows call before the project is installed** (e.g. `tests/tools/db2_image_cache.py`)
  must stay stdlib-only (#5265).
* **A trailing `# comment` on a `.gitignore` pattern line becomes part of the pattern** (`git check-ignore` fails and
  `test_no_page_is_committed_and_each_is_ignored` goes red): put comments on their own line (#5287).
* **X-Ray reads only a file's first 8 KB:** splitting a family into a small new module can pull a long literal (IBM's
  channel-name charset) into that window and trip it (#5289).
* **ruff S608 flags `x + """..."""`** when the string holds SQL-like words; build it with `+=` statements (#5289).
* **`fact_channels.py` must not import the recorder or rehydrator** (import cycle): restore selects get
  `has_table` / `has_column` injected (#5410).
* **`test_java_matrix_gate.py` needs `tests/tools` on `PYTHONPATH`** when run alone (#5382). Raising the Python
  floor drops the old CI matrix legs in the same PR (#5370).

## CI and workflow traps
* On a path-filtered workflow, key caches by `hashFiles` of the inputs, not the sha: the sha only has an entry for
  commits that triggered the workflow (#5184).
* A step that runs `git diff origin/main...HEAD` needs `fetch-depth: 0`; the shallow default has no merge base, so a
  planner silently falls back to "full" (#5191).
* A rerun that "passes on the same SHA" may be main moving under a stale PR: check the failed test against main's
  recent commits before calling it a flake (#5184).
* A cics-crucible `case.json` can list a `sources.copy` directory that is not on disk (git carries no empty dir):
  guard `iterdir()` on case dirs (#5192).
