---
description: "How to use the architecture brief and self-scan SQLite DB to check the blast radius and complexity before editing it, with regen steps and example queries."
---
# Self-scan orientation (token efficiency)

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

GitGalaxy scans its own repo and produces two artifacts specifically to make an LLM coding
session cheaper and safer to run — reach for these *before* an Explore subagent, a broad `grep`,
or reading a large file cold, when the question is really "how big/risky/depended-on is this
thing" rather than "what does this specific code do."

This still applies even when a task already points at exact file/line locations — e.g. a GitHub
issue that quotes the specific lines to change. Knowing *where* to edit isn't the same as knowing
the file's risk standing: check the brief's blast-radius/risk lists (Sections 7, 8, 11) or query
the DB for that file's complexity/fan-in anyway before editing, so "how conservative should this
diff be" is answered from data instead of a guess informed only by the issue text.

- **`docs/gitgalaxy_architecture_brief.md`** — NOT in a checkout: it is published daily to the
  `generated` branch (read it with `python tests/tools/generated_branch.py show
  docs/gitgalaxy_architecture_brief.md`), a byproduct of the CI scan that also produces SARIF/SBOM. This scan
  always installs `tiktoken`/`xgboost`/`pandas`/`numpy` first (`gitgalaxy.yml`'s
  "Install GitGalaxy & Full Precision Engines" step) — confirm by checking the brief's own
  Section 0 traceability table, which reports `Zero-Dependency Mode: Inactive (Full Precision)`.
  Use it for *repo-wide* framing before a large refactor: Section 7 has the actual blast-radius
  ranking ("Top 5 Structural Pillars" by import fan-in, "Top 5 Orchestrators" by fan-out),
  Section 8 has the heaviest functions repo-wide, Section 11 has the top 10 files by cumulative
  risk. If a file you're about to touch shows up in one of these lists, that's a real signal to
  be more conservative (smaller diffs, more explicit tests) — not a vague guess.
- **`docs/self_scan/gitgalaxy_master.db`** (SQLite, via `tests/tools/self_scan.py`) — targeted,
  near-zero-token ad hoc queries about one specific file/function instead of reading the whole
  file just to count its functions or gauge its complexity. **It's gitignored and NOT committed
  on purpose** (a full rescan is ~6-8s, cheaper than storing history) — it may be missing or
  stale in your checkout. Regenerate with `python tests/tools/self_scan.py` (needs `galaxyscope`
  on PATH, i.e. an activated venv with `pip install -e .`), or pull the latest
  `gitgalaxy-self-scan-db` artifact from the most recent push-triggered "Full Report" run of
  `gitgalaxy.yml` on main if you'd rather not run a local scan.
  - Always confirm column names with `.schema <table>` first rather than trusting any list here
    — the recorder schema evolves. Two concrete, verified examples as of this writing:
    ```bash
    # Heaviest/most complex functions in a file before editing it -- avoids reading the
    # whole file just to find what's risky inside it.
    sqlite3 docs/self_scan/gitgalaxy_master.db \
      "SELECT f.func_name, f.complexity, f.loc, f.calls_out_to
       FROM function_data f JOIN file_data fd ON f.file_id = fd.id
       WHERE fd.file_path LIKE '%detector.py%' ORDER BY f.complexity DESC LIMIT 5;"

    # Which directory groups are heaviest, before deciding where new code belongs
    sqlite3 docs/self_scan/gitgalaxy_master.db \
      "SELECT directory_group, COUNT(*) files, SUM(total_loc) loc, SUM(function_count) funcs
       FROM file_data GROUP BY directory_group ORDER BY loc DESC LIMIT 8;"
    ```
  - **Full-precision dependencies required:** every graph column is native and needs
    no optional package (networkx left the runtime in #3041); token mass and the ML columns need
    `tiktoken`, `numpy`, `pandas`, `xgboost`, and `pyyaml` importable in whatever environment runs
    the scan — without all of them, galaxyscope drops into Zero-Dependency Mode and those columns
    come back NULL (`pagerank_score`/`normalized_blast_radius` are computed natively in both modes
    since #3027; `docs/zero_dependency_mode.md` has the per-column list) (this
    is *not* caused by `--db-only` itself, which only selects which recorder writes output; a
    local dev venv missing one of these packages was the actual cause the one time this bit us).
    `self_scan.py` now checks for all five before scanning and aborts loudly if any are missing,
    rather than silently producing a degraded DB — if you hit that, `pip install` whatever it
    lists. CI's copy (the `gitgalaxy-self-scan-db` artifact) always has these installed first, so
    it's always full-precision; only a local run can be affected.
  - **Line numbers:** `function_data.start_line` (with `loc`) is populated, so `path:start-end` for a
    function comes straight from the DB. `python tests/tools/context_pack.py <issue>` does this for an
    issue: it resolves the paths, function/class names and backticked identifiers the issue names and
    prints `path:start-end` pointers (plus one hop of callers/callees and big-file flags) capped at
    ~3k tokens; `--body-file` runs it offline. Ranges are hints from the last scan.
    `--eval N` measures it: for the newest N squash-merged PRs that close an issue it rebuilds the pack as
    of just before the PR and reports how many changed code files the pack names (regenerate the DB at the
    commit under test first; ~10 s plus one `gh` call per issue).
  - **Wiring into `churn worker` (promoter-bot):** before launching a worker, run
    `python tests/tools/context_pack.py <N> --db <worktree>/docs/self_scan/gitgalaxy_master.db` (DB at the
    `origin/main` commit) and append stdout to `prompt.md`. The pack carries its own `## Where to look`
    heading; empty output (nothing resolved) means add nothing; exit 2 means no DB, so skip it.
  - It doesn't parse inside large dict/list literals (e.g. it can't tell you where the
    `"scala"` key starts inside `language_standards.py`'s `LANGUAGE_DEFINITIONS`) — it's for
    orientation and prioritization, not symbol lookup. Read the actual file for that.

Whether the DB pays off for agents is an open experiment: protocol and results in `docs/agents/self-scan-ab-protocol.md` (#4479).
