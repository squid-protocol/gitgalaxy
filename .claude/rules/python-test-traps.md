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
* **Never build JSON by string interpolation in tests when a value is a filesystem path:** use `json.dumps` (Windows
  backslashes) (#5549).
* **`read_text(errors="replace")` on a corpus file in a test fails `tests/test_source_reads.py`:** use
  `gitgalaxy.core.source_text.read_source` (#5658). The same test flags `.decode(..., errors="replace")` in `tests/tools`:
  use `gitgalaxy.core.source_text.decode_bytes` (#6521).
* **`dead_key_audit` flags a constant dict subscript that is read only once** (#5627).
* **`tree_sitter_accuracy_audit.py` takes `--lang <name>`, not `--language`** (#5503).
* **C evaluation order:** `memcpy(b, f(&n), n)` reads `n` before `f` runs; take the pointer into a local first (ASan
  catches it) (#5887).
* **Fixed-format COBOL test input past column 72 is silently truncated by `_code`:** one statement per line in lowering
  tests (#5887).
* **Count maps summed by key are a `Counter`, not `{}`** (a bare dict crashed `--oracle` without tree_sitter, #5533).
* **A bare `(?m)` inside a joined alternation breaks the scan:** use `(?m:...)`. An uppercase `<< CONST` shift reads as a
  heredoc and swallows the file (#5695).
* **`_RET` keyword guard against `class` also blocks `Class<Actor>` return types:** use `class(?![ \t]*<)` (#5535).
* **`ctags --output-format=json --fields=+K` dedupes same-name+pattern tags** (860 vs 939 on doom.go): add `n` when
  counting definitions (#5459).
* **Mode A slicing cuts a unit at the LAST standalone `assembly_returns` match:** where RETURN is an early exit add the
  language to `_NON_TERMINATING_KEYWORDS_BY_LANG` (#5688).
* **`VendorDirectoryDetector.is_candidate_name` is gone:** call `is_vendored(rel_dir)` per ancestor dir (#5515, #5553).
* **Scans are keyed by engine SHA:** to re-score old scans with a new scorer, symlink `<work>/scans/<HEAD sha>` to the
  old scan dir (valid only when `gitgalaxy/` has no diff) (#5617).
* **`tests/fixtures/evidence_report/*` snapshots lag the live translator:** read current holes with `generated_branch.py
  show` (#5775).
* **The shared venv has no pytest-xdist** (`-n4` exits 4); a serial full suite takes ~20 min: poll `full.exit` (#5960).
* **`git archive` honors `working-tree-encoding`:** use `git show rev:path` for raw committed bytes (#6126). Aperture silently
  drops files under a `Build/` directory (#6126).
* **`XGBClassifier` needs scikit-learn:** to run the real-model test install it with `pip --target` into scratch plus
  `PYTHONPATH` (#6129).
* **Put options such as `--max-files-per-commit` before the subcommand:** a positional repo list swallows later flags (#6190).
  Don't use `Closes #N` as a fix label (#6190).
* **The Java crucible leg prints null event values:** a key is present with a null value, so assert `e.get("length") is None`, not `"length" not in e` (#6348).
* **A parametrize value whose repr lands in the test id** (raw bytes) must be deterministic across processes, or xdist
  aborts collection: give lazily-built payloads explicit `ids=` (#6257).
* **A freshness test for a generated list scans tracked files** (`git ls-files`), not whatever is on disk (#6306).
* **A bare `cat > file` (no heredoc) truncates the file to empty:** check `wc -c` before `-F body=@file`, or the PR body
  lands empty (#6323).

## CI and workflow traps
* **Never put a multi-line string inside `${{ }}`** (YAML folds newlines): use two `if:`-gated steps or a block scalar (#5612).
* **Two concurrent `doom_rosetta_check` runs need separate `--work` dirs** (#5960).
* On a path-filtered workflow, key caches by `hashFiles` of the inputs, not the sha: the sha only has an entry for
  commits that triggered the workflow (#5184).
* A step that runs `git diff origin/main...HEAD` needs `fetch-depth: 0`; the shallow default has no merge base, so a
  planner silently falls back to "full" (#5191).
* A rerun that "passes on the same SHA" may be main moving under a stale PR: check the failed test against main's
  recent commits before calling it a flake (#5184).
* A cics-crucible `case.json` can list a `sources.copy` directory that is not on disk (git carries no empty dir):
  guard `iterdir()` on case dirs (#5192).
* When two PRs change the same wait/timeout bound, grep for mirrored planner constants (`det_sweep_plan.DB2_WAIT_S`)
  and update both (#6508).
* **A step that `cd`s into a checkout and pushes needs THAT checkout's `persist-credentials: true`:** a token on a sibling checkout is not used (#6556).
* **Shepherd GraphQL reads:** `timelineItems.totalCount` counts every item type (use `filteredCount` to detect truncation of a filtered connection); `mergeStateStatus` is often `UNKNOWN` (re-read over REST and keep the record only if the head sha matches) (#6539).
* **`test_shepherd_gh.py`:** a test running `sg.main(['reconcile'])` with the real `gh_api` must monkeypatch `ci_digest.main_tip` and `sg._graphql_prs`, or it shells out to `gh` (#6546).
* **A "does not hang" spawn test starts its timeout after the child signals readiness,** not at `p.start()` (#6585).
* **`pr_gates --fast` lint misses `ruff format` drift in tests:** run the pinned `bin/ruff format --check` on your changed test files (#6614).
* **A job-level `if: ... && success()` is false when any ancestor in `needs` was skipped:** use `!cancelled() && needs.<job>.result == 'success'` (#6629).
* **`gh run view --json jobs` has no per-job `createdAt`,** so per-job queue wait can't be read from it (#6633).
* **`ci_digest.PARTS` matches only the expanded job name** (`full-suite part N/M`): a matrix job cancelled before expansion keeps the raw `${{ matrix.group }}` name and triages `real`, so `ci-gate` fails with no test run. After a drop-to-draft cancels a head's runs, read the part jobs' conclusions before hunting a code failure (#7164, #7326).
* **Test stubs that replace a translator method** (`_OverCics`, `no_dto` in `test_det_translate.py`) break on a new keyword arg: grep `dto_for =` / `def no_dto` when its signature changes (#7009).
