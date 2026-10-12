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
whatever noticed. The one exception is the bot's own `gh pr update-branch` (behind main): the bot leaves a marker pair
before and after it, and the approval carries over only through that pair and a first-parent check. With no approval
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
- **Behind main.** A labelled PR that is behind and green gets `gh pr update-branch` from the bot.
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

## Heavy jobs on the PR and again on the push (tested-tree, #4935)

`mainframe-ground-truth.yml` and `smoke-test.yml` run on the PR and again when it merges. Their `tested-tree` job
(`tests/tools/skip_tested_tree.py`, rule and tests in `tests/tools/test_skip_tested_tree.py`) skips the push run when
the merged commit's tree SHA equals the PR head's tree SHA, the commit's parent is in the head (so the PR run's test
merge was that same tree), and the newest `pull_request` run of the same workflow on the head succeeded. Red, cancelled,
in-progress or missing PR runs, a PR that was behind main, a merge commit, a direct push, and every
schedule / `workflow_dispatch` run all run in full; an API error runs too. In smoke-test only the `full-suite` parts are
skipped: the 9-way OS grid is not run on PRs, so it always runs on the push.

Main Watch still gets a verdict: the workflow concludes `success` or `failure` (the gate job always runs), and a skip
is a true green, because that exact tree passed the same workflow on the PR. Main Watch ignores only workflow runs
that conclude `skipped` or `cancelled`. Ground-truth history rows (`--history`) are written by the push run, so the
nightly run writes them too (one row set per day, at that day's HEAD, when a number moved).

## Main is red (main-watch)

`.github/workflows/main-watch.yml` opens one `ci-red-main` issue per workflow that fails on main and closes it when
the workflow next succeeds. Rules live in `tests/tools/main_watch.py` (`decide()` is pure, tested in
`tests/tools/test_main_watch.py`). A run created with the repo `GITHUB_TOKEN` raises no `workflow_run` event (#4859),
so `post-merge.yml` dispatches the Full Suite Gate with `AUTOMATION_PAT` (needs `actions: write`), and an hourly
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
`call-resolution-history.yml`, `graph-comparison-history.yml`, `tree-sitter-accuracy-history.yml`, `tri-comparison-history.yml` and `archetype-validation.yml` no longer open an auto-merged PR into main (they were about 40 of 322 main commits in a week, each queueing every open PR behind it). Each publishes its output files to the `generated` branch with `tests/tools/generated_branch.py publish`, only when the run's ref is `refs/heads/main`; an appended CSV is first restored from `generated` (`fetch`), and `show PATH` reads the published copy, else the committed one. The copies already committed on main are left as they are: frozen, and the seed and fallback. A ledger (`graph_comparison_ledger.json`, `tri_comparison_ledger.json`) keeps its verdicts on main, where people write them; the bot refreshes the counts from main's copy and publishes the result. `tests/tools/test_generated_branch.py` lists every workflow that still commits to main. A first publish needs one `workflow_dispatch` run of each from main.
