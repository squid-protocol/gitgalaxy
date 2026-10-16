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
