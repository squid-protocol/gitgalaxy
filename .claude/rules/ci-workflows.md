---
description: "How to write or change a GitHub Actions workflow here: reach only the PRs it can affect, install only what runs, measure the cost"
globs: ".github/workflows/**"
---
# Writing or changing a workflow (owner 2026-10-24)

CI is the factory's bottleneck: every job runs on one pool of 20 GitHub-hosted `ubuntu-latest` runners, and on a busy
day 40-70 jobs queue behind it (2026-10-24 sample: 18-22 running, queued jobs waiting up to 37 min). A job a PR did
not need delays every other PR. Treat speed as part of the change, not a follow-up.

1. **Reach: run only where a change can affect the result.** A PR-triggered workflow decides in a plan job, from the
   changed files, what it runs. Use `tests/tools/change_classifier.py` (`area()`, the docs-read-by-tests list) and a
   `*_plan.py` beside the existing ones (`ground_truth_plan.py`, `det_sweep_plan.py`, the suite plan, `sweep_plan.py`).
   Never use broad `paths:` like `gitgalaxy/**` or `gitgalaxy/standards/language_standards/**` as the selector: a
   COBOL rule edit must not start the Rust, Go and Java gates. Per-language gates select by the changed language.
   A required check whose plan says "nothing to run" reports success; no workflow-level `paths-ignore` on a required check.
   The plan never skips a job that reads a changed path (over-run, never under-run), and its tests pin both directions.
2. **Install only what the selected gates use.** Toolchain and dependency steps are conditional on the plan
   (`if: contains(needs.plan.outputs.gates, 'rust')`), cached with `actions/cache` keyed by the pin, and fetched once.
3. **Fewer runner requests.** Each job is a queue wait. Prefer one job with parallel lanes over many small jobs when
   setup is short (#5501 measured 5 jobs slower than 1); shard only work that is long in itself.
4. **Drafts and re-pushes.** Heavy jobs skip drafts (#5104, `docs/ci.md`); PR runs set
   `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` so a new push frees the runner.
5. **Measure it, in the PR body.** For a new or changed PR workflow give: runner-minutes per run (from its recent runs
   or `ci_profile`), the share of recent PRs it would run on (replay the plan over the last ~50 merged PRs, as
   `sweep_plan.py --replay` does), and the before/after when the change is a speed change. A new gate adds load to every
   PR it reaches: say why it is worth that, and what it skips.
6. **Spend time on speed.** When you touch a workflow, look at its slowest step in the last runs and cut it (cache,
   narrower corpus or `--samples`, parallel lanes, a cheaper pre-check) before adding more steps.

Edits to `.github/workflows/*` are in scope under the owner's standing grant (2026-10-24), except the shepherd's own
workflows (`shepherd-*.yml`), which still need the owner's OK per PR. Workflow traps (YAML, `run:` quoting, retries):
`.claude/rules/python-test-traps.md` ("CI and workflow traps"); merge labels and the critical path: `docs/ci.md`.
