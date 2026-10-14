# CI: labels that merge a pull request

For maintainers. A label on a pull request tells the CI shepherd what to do with it. You set a **request** label; the
bot sets the **status** labels and posts at most one digest comment per head. Nothing merges unless the required
checks on `main` are green.

## Request labels (maintainers with write access set these)

| Label | What it does |
|---|---|
| `shepherd:merge` | Marks the PR ready and turns on auto-merge (squash). GitHub merges it when the required checks pass. |
| `shepherd:hold` | Never auto-merge. Wins over `shepherd:merge`. |
| `shepherd:matrix` | Runs the full OS x Python matrix (`full-suite-gate.yml`) on the PR's head. Auto-merge stays off until a green run exists for that head. Same-repo branches only; for a fork, run the matrix by hand. |
| `shepherd:full` | The det sweep plans a full sweep instead of narrowing it to the changed cases: the shepherd reruns the latest sweep, which reads the label when it plans. (Label changes do not start the det sweep by themselves.) |

A label added by someone without write access is removed by the bot, with a comment.

**A label is bound to the head it was approved on.** When a maintainer with write access adds `shepherd:merge`, the
bot's own account writes an approval marker naming the head that was labelled (from the event). Only the bot's
markers count; anyone can post a comment. If the head later moves (new commits, a force-push), the label is removed,
whatever noticed. The one exception is a merge of main: a plain merge that brought in nothing but main's changes, or a pre-#5134 bot `update-branch` (a marker pair
before and after it, checked with a first-parent test), carries the approval over. With no approval
marker yet (the labelled run did not happen, or was dropped), the bot does nothing and says so in its log: re-add the
label.

**A dropped approval stays visible.** When the bot removes `shepherd:merge` because the head moved, it comments and
sets `shepherd:reapprove`. That label stays after the request labels are gone, so a PR that lost its approval shows up
in `is:open label:shepherd:reapprove` instead of waiting silently. Re-adding `shepherd:merge` (or `shepherd:hold`)
clears it; so does removing it by hand.

A label added by someone without write access is removed too, on any pass (the timeline names the labeler).

## Status labels (the bot sets and clears these)

| Label | Meaning | What you do |
|---|---|---|
| `shepherd:needs-fix` | A real failure, a merge conflict or a red matrix on this head. One digest comment says what failed and the local command that reproduces it. | Fix it, push. |
| `shepherd:waiting-on-main` | The failing check fails on `main` too. | Nothing on this PR; main's owner fixes it. |
| `shepherd:retrying` | An infra or flake failure is being rerun (up to 3 times, 15 minutes apart). | Nothing; wait. |
| `shepherd:reapprove` | New commits dropped `shepherd:merge` (an approval is bound to its head). | Review the new head, re-add `shepherd:merge`. |

Status labels are cleared when no request label is left, except `shepherd:reapprove` (it marks exactly that case).

## Other rules

- **Depends on #N.** A PR whose body says `Depends on #N` does not auto-merge until #N is merged.
- **Behind main.** Nothing updates a branch just because it is behind (#5134, owner decision 2026-10-14): every push to a ready PR costs one full CI run (superseded-SHA runs were 27% of CI minutes). Workers merge main only when the PR is CONFLICTING/dirty, a required check fails because of main, or golden masters / generated files must be re-blessed after a sibling merge. Main Watch (`ci-red-main`) is the backstop for a bad combination. The classic branch-protection `strict: true` is cleared by the owner by hand; while it is set, GitHub reports a green PR as `behind` and `pr_check` refuses it. Merge-main commits per PR are measured for 3 days after this merged.
- **Infra reruns.** Only a failed job of an infra or flake kind is rerun, and only three times per run.
- **Permissions.** The request labels are honoured only from collaborators with `write`, `maintain` or `admin`.

## Where the logic runs

- `.github/workflows/shepherd-event.yml`: a label added or removed, or new commits (`pull_request_target`).
- `.github/workflows/shepherd-reconcile.yml`: when a workflow behind a required check (or the Full Suite Gate) finishes on a PR, every 20 minutes, or by hand. Each pass reconciles every labelled PR, so a burst of finishing runs coalesces into one pass and nothing waits for the cron (#4935).
- `tests/tools/shepherd_gh.py`: the rules (`decide()` is pure and tested in `tests/tools/test_shepherd_gh.py`).
- Triage and the digest: `tests/tools/ci_digest.py`. Readiness: `tests/tools/pr_check.py`.

Both workflows check out `main` only and never run pull-request code. They use the `AUTOMATION_PAT` secret
(fine-grained, this repository only: contents, pull requests, issues, actions).

To create or refresh the label set (idempotent), run the reconcile workflow by hand with `ensure_labels: true`.

## Fallback

The local shepherd still works from a maintainer's checkout:
`python tests/tools/box/ci_shepherd.py add N` (see its docstring). Use it if the workflows are down.

## Draft PRs skip the heavy workflows (#5104)

The runner pool on a public repository is shared (about 20 concurrent jobs), and every push to a draft PR used to start the
full set of PR workflows: churn workers push WIP to their drafts about every 30 minutes, so approved PRs waited behind runs nobody
needed yet. Now every heavy `pull_request` workflow lists `ready_for_review` in its `types` and every job carries
`github.event_name != 'pull_request' || github.event.pull_request.draft == false`, so a draft starts only the cheap audits
(`ruff-audit`, `mypy-audit`, `small-audits`, `answer-key-guard`). Marking the PR ready (what the shepherd does on `shepherd:merge`)
starts the full set. A skipped job reads as green to a required check, so the shepherd only marks a draft ready in that pass and
enables auto-merge in a later one, and `pr_check.py --merge` marks a draft ready without merging it. A draft cannot be merged,
so no unreviewed code merges. `pull_request_target` (the shepherd's label events) is unchanged. `tests/core_engine/test_workflow_draft_gate.py`
fails when a heavy PR workflow lacks the condition; its allowlist is the cheap audits.

## Heavy jobs on the PR and again on the push (tested-tree, #4935)

`mainframe-ground-truth.yml`, `smoke-test.yml` (its `full-suite` parts) and `java-compile.yml` run on the PR and again
when it merges, because the push run does something a later dispatch cannot: ground truth appends and publishes its history
per push, the full suite is the per-merge regression net, and java-compile's push run seeds the
`java-same-base-<corpus>-<sha>` cache that PRs based on that commit restore. Their `tested-tree` job
(`tests/tools/skip_tested_tree.py`, rule and tests in `tests/tools/test_skip_tested_tree.py`) skips the push run when
the merged commit's tree SHA equals the PR head's tree SHA, the commit's parent is in the head (so the PR run's test
merge was that same tree), and the newest `pull_request` run of the same workflow on the head succeeded. Red, cancelled,
in-progress or missing PR runs, a PR that was behind main, a merge commit, a direct push, and every
schedule / `workflow_dispatch` run all run in full; an API error runs too.

#5129: the gate job itself runs on a main push only (`if: github.event_name == 'push'`). On a PR it could never skip, so it
only took a runner and added a serial queue wait (3-12 min) before the heavy jobs; now a PR push starts the heavy jobs
directly (one job fewer per triggered workflow and PR push). A skipped gate leaves `skip` empty, and the heavy jobs'
`!cancelled() && needs.tested-tree.outputs.skip != 'true'` lets them run. The #4964 members that only checked a merge
(fact-crosscheck, estate-crucible, ports-compile, cics-crucible, unicode-gauntlet, tree-sitter-accuracy-audit) left the
push trigger, and with it the gate, for the post-merge dispatch below (#5131).

Paths filters (#4964): the proof is a `pull_request` run of the same workflow on the head, and GitHub creates that run only
when the PR's own `paths` filter matches. A PR the filter skipped therefore has no run, and the push runs even though its
filter matched on main: a missing run is never a proof. The PR must also have targeted `main`.
`tests/tools/test_tested_tree_workflows.py` pins each workflow's wiring and its PR/push filter pair, so a filter edit is a
reviewed decision, and fails when a workflow on both a PR and a main push has no gate (or a gate has no push to skip).
`java-compile`'s PR run may skip its build when the generated Java equals the base's (`--same-as`); the skipped push is
then the same tree as a base whose own push built it.

Main Watch still gets a verdict: the workflow concludes `success` or `failure`, and a skip is a true green, because that
exact tree passed the same workflow on the PR. Main Watch ignores only workflow runs that conclude `skipped` or
`cancelled`. Ground-truth history rows (`--history`) are written by the push run, so the nightly run writes them too (one
row set per day, at that day's HEAD, when a number moved).

## Post-merge dispatch and its cadence (#4825, #5130, #5131, #5136)

Read-only checks that only need to say whether main is green do not run on every merge. `post-merge.yml` (on each push to
main and every 20 minutes) runs `tests/tools/post_merge_dispatch.py` (tests in `tests/tools/test_post_merge_dispatch.py`).
While any PR job is waiting for a runner it dispatches nothing. Otherwise it dispatches a target on main's head SHA only
when that SHA has no run yet, the target's newest non-cancelled run on main (dispatch, nightly or tag-less push) started at
least `CADENCE_HOURS` (3) ago, and main changed a file the target reads since that run. A failed or truncated comparison
counts as changed. #5136 measured why the cadence matters: idle at dispatch is not idle afterwards. Full Suite Gate, sent
once per main SHA, ran 22 times in 39 hours, took 15.6% of all CI minutes and held 12% of the slots while PRs queued.
Every target keeps a nightly schedule, which covers a day the idle dispatch never fires. The OS grids also run on `v*`
tags. Dispatches use `AUTOMATION_PAT`, so Main Watch sees each verdict, at most one cadence window (plus the idle wait)
after the change that caused it. A red result then covers the range of merges since the last run, not one merge.

| Workflow | Main trigger | Why | Jobs per merge saved |
|---|---|---|---|
| `full-suite-gate.yml` | dispatch (cadence) + nightly + `v*` | #5136: the OS x Python matrix of the whole suite | one ~10-job run per 3 h at most, instead of one per idle SHA |
| `os-smoke-grid.yml` | dispatch (cadence) + nightly + `v*` | #5130: the 9-leg smoke grid moved out of `smoke-test.yml` | 9 (3 macOS) |
| `cics-crucible.yml`, `estate-crucible.yml`, `fact-crosscheck.yml`, `ports-compile.yml`, `unicode-gauntlet.yml` | dispatch (cadence) + nightly | #5131: read-only ratchets; relevance = their own PR `paths` | 1-2 each (the gate, plus the job unless the gate skipped it) when their push paths matched |
| `tree-sitter-accuracy-audit.yml` | dispatch (cadence) + nightly | #5131; relevance is every file (#4599: an engine change outside its PR filter once moved every baseline) | 1-2, on every merge (it had no push filter) |
| `smoke-test.yml` (full suite), `mainframe-ground-truth.yml`, `java-compile.yml` | push (tested-tree) | see the section above | none |
| the `generated` / pages publishers (history bots, evidence pages, generated docs, deploy-docs) | push | they publish from the newest main | none |

Main-side cache saves in the moved workflows (`github.event_name != 'pull_request'`) still happen on a dispatch, which runs
on `main` and so writes the cache scope every PR reads.

## Main is red (main-watch)

`.github/workflows/main-watch.yml` opens one `ci-red-main` issue per workflow that fails on main and closes it when
the workflow next succeeds. Rules live in `tests/tools/main_watch.py` (`decide()` is pure, tested in
`tests/tools/test_main_watch.py`). A run created with the repo `GITHUB_TOKEN` raises no `workflow_run` event (#4859),
so `post-merge.yml` dispatches its targets with `AUTOMATION_PAT` (needs `actions: write`), and an hourly
`reconcile` job reads the latest completed non-cancelled run of each open issue's workflow and comments or closes, so
a dropped event is picked up within the hour. A failure caused only by cancelled legs says so in the comment.

The full-suite jobs (`full-suite-gate.yml`, `smoke-test.yml`) run pytest with `--timeout=600` (`pytest-timeout`): a
hung test fails by name after 10 minutes instead of running the job into its time limit, where it shows as a
"cancelled" leg that names nothing (#4840: the macOS box-tools hang, #4862).

## Nightly blockers baseline (#4863)
Evidence Refresh surveys main once a night; its `publish-blockers` job writes `docs/language_status/blockers/` (blockers.txt/json, meta.json, blockers_history.jsonl with one nightly line) to the `generated` branch, and only when the run's ref is `refs/heads/main`. A dispatch from any other ref lays the same output into a scratch dir and uploads it as the `blockers-generated-preview` artifact; it never writes `generated`. Read the published data with `cics_census.py blockers --generated` / `history show --generated`. Blocker Baseline (`blocker-baseline.yml`) is dispatch-only.

## Evidence pages publish (#4925)
`evidence-pages.yml` writes the `generated` branch only when the run's ref is `refs/heads/main`. A `workflow_dispatch` from any other ref renders the pages into a scratch dir and uploads them as the `evidence-pages-preview` artifact; it never writes `generated` (same rule as the `publish-blockers` job in Evidence Refresh, #4924).

## History bots publish to `generated` (#4847)
`call-resolution-history.yml`, `graph-comparison-history.yml`, `tree-sitter-accuracy-history.yml`, `tri-comparison-history.yml` and `archetype-validation.yml` no longer open an auto-merged PR into main (they were about 40 of 322 main commits in a week, each queueing every open PR behind it). Each publishes its output files to the `generated` branch with `tests/tools/generated_branch.py publish`, only when the run's ref is `refs/heads/main`; an appended CSV is first restored from `generated` (`fetch`), and `show PATH` reads the published copy, else the committed one. The copies already committed on main are left as they are: frozen, and the seed and fallback. A ledger (`graph_comparison_ledger.json`, `tri_comparison_ledger.json`) keeps its verdicts on main, where people write them; the bot refreshes the counts from main's copy and publishes the result. `tests/tools/test_generated_branch.py` lists every workflow that still commits to main. A first publish needs one `workflow_dispatch` run of each from main. #4963 moved two more: `mainframe-ground-truth.yml` (`ground_truth_history.jsonl`, restored by `fetch` before the append and published by its own main-only `publish-history` job, so the job that runs PR code holds no write token) and the rendered evidence report of `evidence-refresh.yml` (`docs/language_status/evidence_report/`, published by its `publish-report` job; the records and the det-sweep ledger stay in the bot PR). Readers use the published copy, else the committed one: `evidence_report.py --check` (the release gate), `estate_intake.py` and `cics_census.py`'s `read_generated` (which has no committed copy, so it errors when nothing is published). The architecture brief written by `gitgalaxy.yml` is still committed to main: agents read it from the checkout, so it needs a reader design first (#4963).

## Full-suite critical path (#5162)
The full-suite parts of `smoke-test.yml` pass `--ignore=tests/cobol_mainframe/test_evidence_components.py`: `mainframe-ground-truth.yml` runs all of `tests/cobol_mainframe/`, so the file (~226 s) ran twice per PR. The OS x Python gate (`full-suite-gate.yml`) still runs it: no other job covers it there. The evidence tests' time was `evidence._match` (fnmatch of every spec pattern against every tracked file, 17M calls per `test_evidence_report.py::test_check_fails_on_an_edited_report`); it now compiles each pattern list once and memoises per (files, spec). `test_evidence_report.py` went from 205 s to about 100 s serial, `test_evidence_components.py` from 60 s to 14 s on its slowest test. The nightly durations cache is still recorded under `-n auto` contention, so summed seconds do not predict a part's wall time: a wall-calibrated weight is not done.
