# CI: labels that merge a pull request

> What has been tried to speed CI up, with the measurements and the ideas that were dropped: `docs/ci_experiments_log.md`.
> Read it before proposing a CI change, and add an entry when you make one.

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

**Bot PRs never get `shepherd:merge` (#6693).** The evidence-refresh bot PR (`auto/evidence-refresh-full`, `auto/evidence-refresh`) merges through its own GitHub auto-merge, which the workflow enables once its checks register. Do not label it: an approval is bound to its head, so each refresh force-push dropped the label and turned auto-merge off again. `evidence-refresh.yml` force-pushes that PR and restarts about an hour of CI, so a dispatch (`gh workflow run evidence-refresh.yml`) while the open PR's head still has checks running stands down and pushes nothing. A manual dispatch is right only after those checks finished, when something merged since that the nightly (03:17 UTC) should not wait for; `-f force=true` overrides the guard and is for a head known to be bad. The hourly dispatches of 2026-10-24..26 ran as `squid-protocol` (the owner's token); nothing in the repo, and nothing in promoter-bot's call-site log (`gh-calls.log`, from 2026-10-24T19:42Z) or `churn-log.md`, dispatches it, so the guard is the fix, not stopping a known caller. The hourly pattern ended on its own after the 2026-10-26T03:16Z dispatch (one more manual run at 2026-10-27T10:30Z); no user systemd timer or crontab on the churn box, no skill or agent under `.claude/`, and no `gh workflow run` in `box/` scripts names this workflow, so the caller was an interactive session on the owner's token, not a scheduled job.

## Status labels (the bot sets and clears these)

| Label | Meaning | What you do |
|---|---|---|
| `shepherd:needs-fix` | A real failure, a merge conflict or a red matrix on this head. One digest comment says what failed and the local command that reproduces it. | Fix it, push. |
| `shepherd:needs-owner` | Auto-merge was refused for good (the shepherd token lacks a permission, e.g. Workflows for a PR that edits `.github/workflows/`). One comment says why; the shepherd stops retrying while it is set. | Merge by hand, or fix the token and remove the label. |
| `shepherd:waiting-on-main` | The failing check fails on `main` too, or did until `main` went green and this head has not been re-tested with the fix. | Nothing on this PR: main's owner fixes it, then the reconcile pass merges `main` in once (#5484) and the label stays until a run on that head finishes. |
| `shepherd:retrying` | An infra or flake failure is being rerun (up to 3 times, 15 minutes apart). | Nothing; wait. |
| `shepherd:reapprove` | New commits dropped `shepherd:merge` (an approval is bound to its head). | Review the new head, re-add `shepherd:merge`. |

Status labels are cleared when no request label is left, except `shepherd:reapprove` (it marks exactly that case).

## Other rules

- **Depends on #N.** A PR whose body says `Depends on #N` does not auto-merge until #N is merged.
- **Behind main.** Nothing updates a branch just because it is behind (#5134, owner decision 2026-10-14): every push to a ready PR costs one full CI run (superseded-SHA runs were 27% of CI minutes). Workers merge main only when the PR is CONFLICTING/dirty, a required check fails because of main, or golden masters / generated files must be re-blessed after a sibling merge. The one exception (#5484, reconcile passes only): a `shepherd:waiting-on-main` PR whose failing check is now green on main's newest commit gets `main` merged in once per main head (`PUT pulls/N/update-branch` with `AUTOMATION_PAT`, a plain merge, so `shepherd:merge` carries over through the bot's marker pair). Not done for a fork, `shepherd:hold`, a conflicting PR (churn fixes those) or a PR that is merely behind. A failure that survives a head containing main's fix is `real`. Main Watch (`ci-red-main`) is the backstop for a bad combination. The classic branch-protection `strict: true` is cleared by the owner by hand; while it is set, GitHub reports a green PR as `behind` and `pr_check` refuses it. Merge-main commits per PR are measured for 3 days after this merged.
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

## Learned flakes

A check that `flake_history.py` learned is flaky (passed on a rerun at least 3 times, 80% of its reruns, last 14 days)
gets one automatic rerun for its first failure instead of going to a fixer as `real`. `shepherd_gh.py reconcile --flake-cache FILE`
(or `$SHEPHERD_FLAKE_CACHE`) reads `flake_history.json`; it never scans. No cache means no learned flakes, never a wait.
Both shepherd workflows restore the file from the Actions cache (`flake-history-*`, newest wins) and pass `--flake-cache`;
`shepherd-reconcile.yml` also runs `flake_history.py --refresh-only` when it is over 6 hours old (best effort, 12 minute cap)
and saves the cache even when the pass failed (#5398).

## Shepherd conditional reads across passes (#6534)

With `SHEPHERD_API_CACHE=<dir>` set, `shepherd_gh.py` reads through `pr_check.conditional_api`: each GET sends the kept
ETag as `If-None-Match`, and a 304 (no REST quota) returns the body kept in `<dir>`. Entries are written atomically
(temp file, rename), a corrupt or etag-less entry is a plain read, and every pass ends with `pr_check.prune_api_store`
(entries older than 7 days, and beyond 2000, are dropped). Unset, reads are plain. The directory is meant to be
restored and saved by `actions/cache` between passes; that wiring lives in `shepherd-*.yml` (owner OK per PR) and is not
applied yet. A `workflow_run` pass has a read-only cache token (see `shepherd-reconcile.yml`), so it can restore but
not save: the save has to come from a workflow that may write the cache.

## Fallback

The box shepherd (`tests/tools/box/ci_shepherd.py`) is retired as the live shepherd (#5398) but still works from a
maintainer's checkout:
`python tests/tools/box/ci_shepherd.py add N` (see its docstring). Use it if the workflows are down.

## Changing the shepherd or label workflows

- **Level-triggered.** Decide from the PR's current state on every pass, never from the event that woke you, and keep
  every action idempotent: GitHub drops, delays and reorders events.
- `labeled` / `unlabeled` events carry no `commit_id`; read the head from the PR.
- A bot status label must never start CI.
- A skipped required check counts as passing, so no trigger or filter may skip `det`.
- Test on a real PR with replayed lag and overlapping runs, not only `test_shepherd_gh.py`.
- The workflows run `main`'s code, so a fix to the shepherd itself is merged with the local
  `tests/tools/box/ci_shepherd.py`. After it lands, restart any long-running local shepherd.
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

## Critical path: ground-truth as a warm job and 4 parts, evidence deltas apart (#5133, #5543)

`ground-truth` (a required check) aggregates `ground-truth-warm` and `ground-truth-part` 1/4..4/4, as `full-suite` aggregates its parts.
The warm job pays the warm-up once: it fetches the corpora, scans all of them in parallel, runs the ledger gate (summary and history
append) and uploads the scans (`_scans`, tarred because upload-artifact skips hidden paths) as `ground-truth-scans`. Each part restores the
clones, unpacks those scans (the engine key is this commit's HEAD, the same in every job of the run, so they count as cached) and runs its
pytest share, so no part re-runs the gate and no test pays a cold scan. pytest-split cuts
`tests/cobol_mainframe/` between the parts (`--splits 4 --splitting-algorithm least_duration`, over the committed
`.test_durations`, so all parts cut one split; no hand-listed files, a new test is placed by its recorded seconds). Refresh the
ground-truth tests' seconds in `.test_durations` from the `test-times-ground-truth-part-N` artifacts of a main run
(`tests/tools/merge_test_durations.py`): smoke runs have no corpora, so the corpus tests are recorded as skipped. The advisory evidence level deltas are the `evidence-deltas` job of `smoke-test.yml`
(`continue-on-error`, not in `full-suite`'s needs). The smoke full-suite parts balance by the newest nightly's durations cache (#4847), falling back to the committed
`.test_durations`, which the ground-truth parts and the OS-matrix gate always read.

**Measured after #5264 (before #5543's warm job; the 2-part layout) (main push run 39108505757, 2026-10-18).** `ground-truth part 1/2` 11.0 min, `part 2/2` 11.3 min (the
aggregate `ground-truth` check green about 1 min later), against one job of about 14-16.5 min before the split: the parts are
within 3% of each other and time-to-green on this check fell by 3-5 min. `.test_durations` had no seconds for 696 of the
5782 `tests/cobol_mainframe/` tests the parts ran and a stale value for 86 more; it is now refreshed from that run's
`test-times-ground-truth-part-N` artifacts (the two files hold disjoint halves, so `merge_test_durations.py` merged them with
no conflict), and a replay of `least_duration` over it gives two parts of 1354 s each. The full-suite after-numbers need a
completed main smoke run after #5264: run 39108505787 was superseded (part 2 cancelled), so they are not recorded here.
`test_the_ground_truth_seconds_are_recorded_and_the_parts_balanced` pins both facts. The 8 warnings `time_ratchet.py check`
now prints (10-11.4 s tests under `-n auto` contention in the ground-truth job) fail nothing: the limit is 15 s.

**Cached scans and the queue-depth layout (#5616, #5543).** The warm scans are saved as an `actions/cache` entry on main only (key: `corpora.json` plus the engine-state hash, #5024). `plan` looks the key up (`lookup-only`): on a hit the warm job is skipped, the parts restore the scans and part 1 runs the (cheap) ledger gate; on a miss (a PR that changes engine code) the warm job runs as above. `plan` also counts queued PR jobs with the signal `post_merge_dispatch.waiting_pr_jobs` (`tests/tools/ci_layout.py`): above `BUSY_ABOVE` (8) a pull request gets the *busy* layout, 2 parts with no warm job that each warm their own scans (the pre-#5559 shape: 2 runners instead of 5 and no serial warm-up queue); push, nightly and manual runs are always calm. **Since the #5543 follow-up, a pull request has no warm job on a cache miss either** (calm or busy): it was a fourth serial queue wait (plan, warm, parts, final) and a fifth runner request, so the 4 parts scan for themselves (part 1 all 8 corpora and the gate, the others only what their pytest share reads). Push, nightly and manual runs keep the warm job: it saves the scans cache and appends the history. Not yet measured on CI: compare calm cache-miss PR runs before and after (wall, runner-minutes, part 1 against the other parts) before reading it as a win; reverting is one line in `ci_layout.choose`. `plan` writes the chosen layout and why to its job summary and each part records it, so timings can be split by layout. The required check stays the final `ground-truth` job in every layout. The engine-state hash leaves out the COBOL-to-Java translator (`tools/cobol_to_java` except `det/copy`, and the two controllers): a scan never imports it, so a translator commit keeps the cached scans. `test_ground_truth_scan_key_workflow.py` fails if a file the scan imports or reads falls out of the key. A part with no warm job and no cached scans (the busy layout) scans only the corpora its pytest share reads (#5543 option (b)): it collects its share (about 7 s), and `tests/tools/ground_truth_corpora.py` maps the few tests that read a scan DB to their corpora; part 1, which runs the ledger gate, still scans all 8, so this saves runner-minutes in the other parts, not wall time. A lookup that fails scans every corpus.

**Measured (2026-10-22, #5543).** Evenly spaced samples of successful first-attempt runs of this workflow whose parts ran (`plan`-only skips left out); wall = `run_started_at` to `updated_at` (queue included); runner-min = the sum of every job's run time; critical path = plan + warm + slowest part + final job, run time only. The window for each row is the code that was on main: before #5559 (2 parts, 2026-10-17..19), after #5559 only, after #5616 (2026-10-20..22).

| layout | runs | wall median | runner-min median | critical path (run time) | queue wait summed over jobs |
|---|---|---|---|---|---|
| 2 parts (before #5559) | 21 | 19.6 min | 19.2 | 12.2 min | 7.8 min |
| warm + 4 parts (#5559 only) | 23 | 18.5 min | 21.1 | 9.8 min | 15.5 min |
| warm + 4 parts, cache miss (after #5616) | 6 | 19.6 min | 17.2 | 8.6 min | 12.6 min |
| 4 parts, cache hit (after #5616) | 6 | **7.5 min** (max 7.9) | **10.9** | **3.6 min** | 2.9 min |
| busy: 2 parts (after #5616) | 8 | 19.1-20.1 min | 13.2-17.1 | 7.4-10.0 min | 12.6-16.1 min |

Reading it: with the cache hit the check is at the 7.5 min target and uses about 45% fewer runner-minutes than the 2-part layout; the parts run 2-3 min each once nothing scans cold. Every other layout is dominated by queue waits (13-16 min summed over 3-5 serial jobs) while the repo's runner pool is full, not by compute: their wall time is about 19-20 min whichever layout ran, so the layout choice does not move it. Of the 20 post-#5616 runs sampled, 12 ran calm (6 cache hits, 6 misses) and 8 ran busy (2 of those also restored cached scans): both the cache-hit and the busy layouts have run on CI. The layouts are small samples (6-8 runs); treat a gap under a minute as noise. What would move the miss and busy rows is runner supply or fewer serial jobs, not another split. `.test_durations` was stale for these parts: it held 5747 of the 7079 `tests/cobol_mainframe/` tests the parts ran and its seconds summed to 2705 against 1298 measured on a warm-cache main run (39774013849). A replay of `least_duration` over the old file planned four equal 833 s parts that actually took 279-378 s (spread 26%); it is refreshed from that run's `test-times-ground-truth-part-N` artifacts, and the replay now plans four 325 s parts.

**Re-measured after #6494, #6146 and #6579 (2026-10-25, #5543).** Same method as the table above, over every successful first-attempt PR run created after #6579 merged (03:12Z) in which the parts ran: 3 runs, all in the *busy* layout (2 parts, no warm job), one of them (40157530558) restoring cached scans. No calm cache-hit run fell in the window, so that row is not re-measured; the 7.5 min above stands for it. Critical path = plan + slowest part + final job, run time only.

| layout | runs | wall median | runner-min median | critical path (run time) | queue wait summed over jobs |
|---|---|---|---|---|---|
| busy: 2 parts (after #6579) | 3 | 18.0 min (15.9-30.2) | 10.7 (9.4-13.6) | 5.6 min (5.1-7.5) | 14.4 min (13.3-29.7) |

Reading it: runner-minutes fell from 13.2-17.1 to 9.4-13.6 (median 10.7) and the compute critical path is 5.1-7.5 min, inside the 7.5 min target in every run. The wall time of a busy run is still 16-30 min because 13-30 min of it is queue wait over the plan, part and final jobs, which the layout cannot remove. Where a part's time goes (steps of 15 s or more, busy runs): part 1 pays `Scan the pinned corpora` 103-135 s when no scans are cached (it scans all 8 for the ledger gate), the ledger gate 16-28 s and its pytest share 132-235 s; part 2 now scans 19-32 s (only the corpora its share reads, #6579) and its share takes 180-317 s. So #6579 took the scan out of part 2; the one remaining scan cost is part 1's, and only on a cache miss. The part-1 scan is not the wall-time bottleneck: it is under 2.3 min against 13+ min of queue wait. The check meets the 7.5 min target on compute and on a cache hit; a miss or busy PR run stays queue-bound until runner supply or the number of serial jobs changes. The sample is 3 runs: read gaps under a minute as noise.

**Re-measured after #6597 (2026-10-25, #5543).** Every successful first-attempt PR run created after #6597 merged (06:38:46Z) in which the parts ran: 29 of the 35 successful first-attempt runs (the rest were `plan`-only), read with `gh run view --json jobs`. Wall = first job start to last job end (the wait for `plan`'s own runner is left out; waits between jobs are in); runner-min = sum of each job's run time rounded up per job; critical path = plan + slowest part + final job, run time only. Layout from the shape of the run: 4 parts is calm (no warm job on a PR), 2 parts is busy; a calm run with no scan step in its parts hit the scans cache.

| layout | runs | wall median | runner-min median | critical path (run time) | slowest part |
|---|---|---|---|---|---|
| calm, cache hit (4 parts) | 2 (40170716593, 40187244914) | 14.9 min (6.9-22.9) | 17.5 (17-18) | 5.1 min (4.6-5.5) | 3/4, 1/4 |
| calm, cache miss (4 self-warming parts) | 3 (40175823564, 40176206177, 40186421014) | 10.2 min (9.3-20.5) | 24 (22-29) | 6.7 min (5.6-8.5) | 1/4 twice, 4/4 once |
| busy (2 parts) | 24 | 29.2 min (9.4-48.4) | 13.5 (10-19) | 7.1 min (4.7-10.7) | 1/2 in 20 of 24 |

Reading it: on compute every calm run is inside the 7.5 min target except one cache-miss run (8.5 min, the 29-runner-min run with part 1 at 8.1 min). Without the warm job, a calm cache miss pays about 107-194 s of cold scan in every part that scans, so it costs 22-29 runner-min against 17-18 on a hit and a median 13.5 for a busy 2-part run: the saved serial wait (no `warm` job) is bought with runner-minutes, as the #6597 body predicted. Part 1 is the slowest part in 2 of 3 miss runs (scan of all 8 corpora, then the gate, then its share) but only by 0.5-3 min, so it is not a new critical path of its own. The busy layout is the slow one on wall (median 29.2 min over 24 runs, inter-job waits included) while its compute is 7.1 min: it is queue-bound, as before. A calm run's wall (6.9-22.9 min) swings with how long its 4 parts wait for runners, so the 7.5 min wall target holds only in the quietest runs (6.9 min, one hit run). Samples are 2 and 3 runs for the calm rows: read gaps under a minute as noise, and the calm-miss verdict (keep `warm=False` on a PR) as "no evidence against", not a proven win. Not changed here: `ci_layout.choose` stays as #6597 left it.

**Folding `plan` or the aggregate into the parts: measured, not done (2026-10-25, #5543).** The wall time is queue-bound over the serial `plan`, part and `ground-truth` jobs, so the next idea was to drop one of them. Replaying `ground_truth_plan.py` over the last 60 merged PRs (changed files from the PR files API): 14 are mode `none` (23%), 46 are `full`. Two facts decide it:
- The aggregate cannot fold into a part: the ruleset names `ground-truth`, a matrix job cannot carry that name, and an aggregate inside a part would have to poll its siblings on a held runner.
- Folding `plan` into the parts needs a static 4-part matrix (a matrix is sized before any step runs). Each part would run the planner itself, which is cheap, but the layout choice cannot move into the parts: they read the queue at different seconds and could disagree on `--splits`. So the busy layout (2 parts) would go. Busy was 24 of the 29 part-running runs after #6597 (83%), and it is the layout that spends the fewest runners (13.5 runner-min median against 17-29 for calm). The 23% of PRs in mode `none` would also start 4 runners to report nothing, where they use one today.

Net: one fewer serial wait for the 77% of PRs that run, bought with 4 runner requests instead of 2 in the layout 83% of them use, on a pool whose queue is the problem. No evidence that wins, so `plan` and the aggregate stay. What would change it: a way to choose the part count without a job (a repository variable set by the shepherd from the queue depth), or runner supply that stops queueing. CICS Crucible (#5530, closed) already sizes its shards in its own `plan` job and reads the queue (#5919); folding its `plan`/`crucible` jobs has the same trade-off and is not measured here.

**Calm cache hit, third look; CICS Crucible fold measured (2026-10-25, #5543).** Same method as the #6597 table, over the 46 successful first-attempt `ground-truth` PR runs created after 06:38:46Z. Calm cache hits are still **2** (40170716593, 40187244914): the one calm run added since the last look (40192762307, 4 parts) was a cache *miss* (parts 1, 3 and 4 scanned 128-142 s each, part 2 18 s; wall 11.9 min, 23 runner-min, compute 5.8 min), so the calm-miss row is now 4 runs and the hit row cannot be called a 3-sample median. Read the 7.5 min wall as unconfirmed for a hit, not as met or missed; the cache is saved on main only, so a hit needs a PR whose engine-state hash equals a main commit's, and few PRs touch no engine file. Re-run this when a third calm hit appears. For `cics-crucible.yml` (#5530, #5919): 72 successful first-attempt PR runs since 2026-10-24T12:00Z ran the shards (49 more were skipped by the workflow's paths), every one with the same 5 jobs (`plan`, `runner-tests`, 2 `measure` shards, `crucible`). Medians: wall 19.9 min (7.8-42.6), 16.5 runner-min (13-54), compute critical path (`plan` + slowest shard + `crucible`) 6.0 min (4.4-20.0). `plan` runs 0.1 min (max 2.2) and `crucible` 0.5 min (0.4-0.8): together about 12% of the runner-minutes and 0.6 min of compute, while the wall is again queue-bound (14 min above compute). Folding them would save at most two runner requests of five and up to two queue waits, and costs the same two things as the `ground-truth` fold above: the 2-shard matrix would become static (`plan` sizes it from the cases, #5919), and the required check name would need to stay on a job that is not a matrix leg. Not done: no change to `cics-crucible.yml`; the fold stays a candidate only if the shepherd can publish the shard count without a job.

**Calm cache hit, fourth look (2026-10-26, #5543).** Same method as the #6597 table, over the 116 successful first-attempt `mainframe-ground-truth.yml` PR runs created after 06:38:46Z on 2026-10-25, 101 of which ran the parts (read with `gh run view --json jobs`; hit = a part's `Restore the cached scans` step succeeded, miss = its `Scan the pinned corpora in parallel` step ran; 4 parts is calm, 2 is busy). Wall = first job start to last job end; runner-min = per-job minutes rounded up and summed; critical path = plan + slowest part + final job, run time only. A third calm hit exists now (22 of them), so the hit row is a real median:

| layout | runs | wall median (range) | runner-min median (range) | compute critical path median (range) |
|---|---|---|---|---|
| calm, cache hit (4 parts) | 22 | 11.2 min (4.8-25.9) | 18 (15-19) | 4.8 min (3.5-5.5) |
| calm, cache miss (4 self-warming parts) | 13 | 14.0 min (8.3-25.2) | 25 (22-29) | 7.4 min (5.8-8.5) |
| busy, restored scans (2 parts) | 39 | 21.1 min (7.9-41.4) | 13 (10-15) | 6.6 min (4.5-7.4) |
| busy, self-warming (2 parts) | 27 | 23.9 min (6.6-36.2) | 16 (13-19) | 8.9 min (5.7-10.7) |

Reading it: the 7.5 min target is met on compute by every layout's median except busy self-warming, and by the calm cache hit with room to spare (4.8 min). It is **not met on wall**: the calm cache hit median is 11.2 min, 3.7 min over, and only the quietest runs (4.8 min minimum) reach it, because the plan, part and final jobs each wait for a runner. So #5543 stays open: the remaining gap is runner-pool queueing, not compute, and the open ideas are unchanged (fold `plan`/`final` into the parts, measured and not done above; the same layout for #5530 and #5562). The wall column includes queue time between jobs, which swings with the pool, so read gaps under a minute as noise. No change to `ci_layout.choose` or any workflow.

`ground-truth` also has a `plan` job (#5164, `tests/tools/ground_truth_plan.py`, as `det` has `det_sweep_plan.py`): a PR whose every changed file is a provable non-input (docs outside `docs/language_status/`, `.claude/`, churn / shepherd tooling, workflows and test directories the job does not read) skips both parts and passes in about a minute. The list is an allow-list of what the job does not read: an unlisted file is an input, and push, nightly and manual runs are always full.

**Push re-runs: no approval gate added (2026-10-28, #6278 item 6).** Item 6 asked to extend the draft rule so heavy jobs wait for review approval or `shepherd:merge`. Measured first, over the 24 newest merged PRs (issue timelines: commit, `ready_for_review` and `shepherd:merge` label times): 67 commits, 55 of them pushed while the PR was still a draft (cheap audits only already), 12 after it was marked ready, and **0** pushed while the PR was non-draft and not yet labelled. Churn PRs open as drafts and the shepherd marks them ready only on `shepherd:merge`, so the window the extension would close is empty. The 12 post-ready commits are fix rounds on a PR already queued for merge; they need a fresh full run, so gating them would only delay the check the merge waits on. An approval gate would also mean adding `labeled` and `pull_request_review` to the `types` of all ~24 heavy workflows, and any other label event (status labels) would then start, or cancel via `cancel-in-progress`, a run. Not done: re-measure if non-draft unlabelled pushes appear (a human-opened ready PR).

## Heavy jobs on the PR and again on the push (tested-tree, #4935)

`mainframe-ground-truth.yml`, `smoke-test.yml` (its `full-suite` parts), `java-compile.yml` and `equivalence-e2e.yml` (#5954 slice 4) run on the PR and again
when it merges, because the push run does something a later dispatch cannot: ground truth appends and publishes its history
per push, the full suite is the per-merge regression net, and java-compile's push run builds main's tree. Their `tested-tree` job
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
then the same tree as a base whose own push built it. The base's generation comes from the `java-same-base-<corpus>-<content hash>`
cache, which `java-base-generation.yml` seeds on every main push that touches the generation inputs (#5142): not in
java-compile's push run, which is cancelled by the next push (#4825) or skipped by tested-tree and so saved nothing, leaving
most PRs to regenerate the base's two paths (dsf: 420-520 s). Its per-sha concurrency group never cancels, and a lookup-only
restore makes a push whose content key exists cost seconds.

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
| `crucible-path-independence.yml` | dispatch (cadence) + nightly | #6670: scan-vs-scan determinism; relevance = its own PR `paths` | none on main (it had no main trigger); see below for the PR side |
| `tree-sitter-accuracy-audit.yml` | dispatch (cadence) + nightly | #5131; relevance is every file (#4599: an engine change outside its PR filter once moved every baseline) | 1-2, on every merge (it had no push filter) |
| `smoke-test.yml` (full suite), `mainframe-ground-truth.yml`, `java-compile.yml` | push (tested-tree) | see the section above | none |
| the `generated` / pages publishers (history bots, evidence pages, generated docs, deploy-docs) | push | they publish from the newest main | none |

**Not on PRs either (#6670).** `fact-crosscheck.yml`, `unicode-gauntlet.yml`, `estate-crucible.yml` and `crucible-path-independence.yml` did not fail once on a pull request in the 7 days to 2026-10-25 (702, 458, 280 and 275 runs), while each took a runner from the PR pool (about 3.4, 3, 0.5 and 5.2 min of job time). Their jobs now skip on `pull_request` (`if: github.event_name != 'pull_request'`, no runner), and they run only from the dispatch above and their nightly. The `pull_request` trigger and its `paths` stay on purpose: they are the `from-pr-filter` relevance patterns, and `test_engine_reach_workflows.py` / `workflow_inputs.py` keep proving them. The three ratchets are still met before a push by `pr_gates.py --ratchets` / `--fast` (the PR-worker agent and the det-port / cics skills run them), so a fix still lowers its ledger in its own PR; a regression that slips through opens `ci-red-main` within one cadence window. `test_post_merge_dispatch.py` pins the four. The security scans (CodeQL, Muninn, the Zero-Trust pre-gate) stay on every PR (owner decision, 2026-10-25).

Main-side cache saves in the moved workflows (`github.event_name != 'pull_request'`) still happen on a dispatch, which runs
on `main` and so writes the cache scope every PR reads.

**No cache is saved by a pull request (#6675).** On 2026-10-25 the Actions cache held 10.69 GB in 127 entries against GitHub's 10 GB limit, the oldest last read 10.6 h earlier: past the limit GitHub evicts the least recently used, so a cache main saved lived about half a day (`cache-prune.yml` trims nightly, and PRs refilled it within ~12 h). A PR's save is scoped to its own ref, which no other PR reads, and 20 combined `actions/cache` steps in 7 PR workflows still saved there (2.18 GB of scip-java from graph-accuracy alone, which never ran on main; 9 PR copies of `db2-odbc-cli` re-saved after main's was evicted). Each is now `actions/cache/restore` plus an `actions/cache/save` at the end of its job that runs only off pull requests and only on a miss (continue-on-error, as #5024 did for the corpora); setup-go's built-in cache is off on a PR; graph-accuracy-audit.yml has a nightly run that seeds its caches on main (and Main Watch watches it). `test_cache_keys.py` fails on a combined cache step in a PR workflow and on a save a PR can reach.

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
A customer's blocker list comes in two forms from one run, a full report and a salted-hash anonymized twin they can send us: `tests/tools/blocker_report.py`, schema in `docs/language_status/blocker_report_schema.md` (#5054).
Evidence Refresh runs `tests/tools/blocker_estate_feed.py` on the survey it just cached (a `continue-on-error` step): each burned estate (and the cics-crucible cells) goes through `blocker_report` and `blocker_ingest` as a customer's report would, and the step fails when a ledger row's category or counts differ from the full report, a catalogued signature does not link to its issue, ids change under the same salt or stay equal under another, or a source identifier of the estate appears in the anonymized output. The step runs with `--require-sources`, so it also fails when an estate's sources are not found (the leak scan must run on every burned estate and the cics-crucible checkout, #5054 done-when 2). `feed.json` lists the rows that match no issue yet; `publish-blockers` lays it on `generated` as `docs/language_status/blockers/blocker_feed.json`, and `blocker_estate_feed.py queue --generated` turns it into the churn queue (drafted issue bodies, deduped by row id) (#5054).

## Evidence pages publish (#4925)
`evidence-pages.yml` writes the `generated` branch only when the run's ref is `refs/heads/main`. A `workflow_dispatch` from any other ref renders the pages into a scratch dir and uploads them as the `evidence-pages-preview` artifact; it never writes `generated` (same rule as the `publish-blockers` job in Evidence Refresh, #4924).

## History bots publish to `generated` (#4847)
`call-resolution-history.yml`, `graph-comparison-history.yml`, `tree-sitter-accuracy-history.yml`, `tri-comparison-history.yml` and `archetype-validation.yml` no longer open an auto-merged PR into main (they were about 40 of 322 main commits in a week, each queueing every open PR behind it). Each publishes its output files to the `generated` branch with `tests/tools/generated_branch.py publish`, only when the run's ref is `refs/heads/main`; an appended CSV is first restored from `generated` (`fetch`), and `show PATH` reads the published copy, else the committed one. The copies already committed on main are left as they are: frozen, and the seed and fallback. A ledger (`graph_comparison_ledger.json`, `tri_comparison_ledger.json`) keeps its verdicts on main, where people write them; the bot refreshes the counts from main's copy and publishes the result. `tests/tools/test_generated_branch.py` lists every workflow that still commits to main. A first publish needs one `workflow_dispatch` run of each from main. #4963 moved two more: `mainframe-ground-truth.yml` (`ground_truth_history.jsonl`, restored by `fetch` before the append and published by its own main-only `publish-history` job, so the job that runs PR code holds no write token) and the rendered evidence report of `evidence-refresh.yml` (`docs/language_status/evidence_report/`, published by its `publish-report` job; the records and the det-sweep ledger stay in the bot PR). Readers use the published copy only (main commits none, #5206; `evidence_report.py` fetches it into the git-ignored directory): `evidence_report.py --check` (the release gate), `estate_intake.py` and `cics_census.py`'s `read_generated` (which has no committed copy, so it errors when nothing is published). The architecture brief written by `gitgalaxy.yml` is published too (#5469): main-only, untracked and git-ignored, read with `python tests/tools/generated_branch.py show docs/gitgalaxy_architecture_brief.md`. Nothing but the approval inputs (evidence records, det-sweep ledger) is committed by a bot to main now.

## Full-suite critical path (#5162)
The full-suite parts of `smoke-test.yml` pass `--ignore=tests/cobol_mainframe/test_evidence_components.py`: `mainframe-ground-truth.yml` runs all of `tests/cobol_mainframe/`, so the file (~226 s) ran twice per PR. The OS x Python gate (`full-suite-gate.yml`) still runs it: no other job covers it there. The evidence tests' time was `evidence._match` (fnmatch of every spec pattern against every tracked file, 17M calls per `test_evidence_report.py::test_check_fails_on_an_edited_report`); it now compiles each pattern list once and memoises per (files, spec). `test_evidence_report.py` went from 205 s to about 100 s serial, `test_evidence_components.py` from 60 s to 14 s on its slowest test. The nightly durations cache is recorded under `-n auto` contention and scaled to each part's pytest wall (#5133 below).

## Full-suite parts balanced by `least_duration` (#5133)
Main run 38835555699: part 1 took 11.9 min, part 2 4.8, part 3 3.5. Cause: pytest-split's default `duration_based_chunks` cuts contiguous slices of the collection, and the committed `.test_durations` had no entry for 4014 of 21385 tests (1707 in `tests/cobol_mainframe`, 1202 `core_engine`), each weighed at the 0.2 s average. Replayed offline against the real per-test seconds of that run (`test-times-part-*`): the old split gave 2534 / 857 / 558 s per part; `least_duration` on the same stale file gives 1338 / 1290 / 1322 s, and on the refreshed file 1317 s each. The full-suite step now passes `--splitting-algorithm least_duration` and `.test_durations` is refreshed from that run's times artifacts (21384 tests, 2 unrecorded. `time_ratchet.py check` on the committed `.test_durations` (no slow marks in that file) reads `pytest.mark.slow` from the test sources (`slow_marks_from_source`), as conftest.py does at run time; the 15.1 s `test_evidence_report.py::test_the_release_gate_passes_...` is a baseline entry (15.06 s). The nightly recorder is still contended `-n auto` seconds; since the weights only order tests, a uniform contention factor does not change the split.

**Measured after #5543 (8 completed main push smoke runs, 2026-10-22, job start to end).** Part 1 / 2 / 3 averaged 4.6 / 4.8 / 4.3 min, so the means sit within 14% of each other. Per run the slowest part is 4.3-5.9 min (mean 5.3), against 21.4 min for part 3 before #5133 (parts were 21.4 / 12.8 / 9.3). The "within about 20%" acceptance is not met per run: max/min of the three parts was 1.24-1.77 (median 1.4), and 0 of the 8 runs were within 1.2. The spread is run-to-run noise on shared runners (the same part moves 200-350 s between runs) on top of the nightly durations being recorded under `-n auto` contention, which a split by recorded seconds cannot remove; a wall-calibrated recording is the remaining slice.

**Wall-calibrated recording (#5133 slice 2).** The nightly parts now write their pytest-step wall seconds and scale their `--store-durations` file so it sums to that wall (`tests/tools/calibrate_test_durations.py`, `smoke-test.yml`) before `full-suite-durations` merges them. The wall includes collection and worker start-up, a per-part constant folded into the weights. The nightlies of 2026-10-20..22 were all cancelled, so no calibrated cache exists yet and the balance after this change is not measured: re-measure part 1/2/3 times (max/min against the 1.2 target) on the main push runs after the first completed nightly. Runs: 39868125440, 39864777446, 39863347779, 39858049216, 39854833642, 39853464421, 39845355686, 39842093955. Ground-truth (runs 39883321540, 39878626772): warm job 2.5-4.5 min, then 4 parts of 2.3-2.7 min each, the aggregate check green 14-23 min after the first job started (waits for the 4 parts to get runners, 7 min in the slower run), against 14-16.5 min for the single job before.

**Why no calibrated cache exists (#5133 slice 3).** The nightly ran in main's concurrency group (`smoke-test.yml-refs/heads/main`) with `cancel-in-progress: true`, so the next main push cancelled it about 5 min in: all 8 nightlies of 2026-10-15..22 ended `cancelled` (run 39755738950: the three parts cancelled 5 min after start, `full-suite-durations` never ran), and the only durations cache is still `test-durations-38247246921` (2026-10-12). Slice 4 fixes it: the `schedule` event now runs in its own `nightly` group (`smoke-test.yml`) with `cancel-in-progress` off for it, so a push no longer cancels it (a second nightly would queue behind a running one; `tests/core_engine/test_smoke_test_concurrency.py` pins the group and cancel setting for schedule, push, PR and dispatch). Balance before (unchanged, the 8 runs above): max/min 1.24-1.77, median 1.4, 0 of 8 within 1.2. Balance after: not measured; it needs the first completed nightly (04:23 UTC) and then the main push runs that restore its cache. Re-measure then, and fix the weights if max/min is still above 1.2.

**Re-measuring (#5133 slice 5).** As of 2026-10-24 no nightly has completed (the six before #6462 were cancelled; the newest durations cache is still `test-durations-38247246921`), so the balance after calibration is still unmeasured. `python tests/tools/ci_part_balance.py --latest 8` (or run ids) prints each run's part minutes and max/min against 1.2; run it on main push runs after the first completed nightly and compare with the 8 runs above. Two runs read on 2026-10-24 (40085990351, 40085036758, still the 2026-10-12 cache) gave 1.72 and 1.65.

**Re-measuring (#5133 slice 6), 2026-10-25.** Still unmeasured. At 09:23 UTC the 2026-10-25 nightly (run 40179743618, created 09:13) was `queued` with `suite-plan` not started, and the newest durations cache was still `test-durations-38247246921` (2026-10-12), so no calibrated cache exists and main push runs cannot have restored one. `calibrate_test_durations.py` is unchanged: its weights are tuned only after a measurement shows max/min above 1.2. Next step: once that nightly completes and 3 or more main push runs have restored its cache, run `python tests/tools/ci_part_balance.py --latest 8` and compare with the 8 runs above (max/min 1.24-1.77, median 1.4).

**Re-measuring (#5133 slice 7), 2026-10-25.** Still unmeasured. The 2026-10-25 nightly (run 40179743618) was `in_progress`: `suite-plan`, parts 2/3 and 3/3 had passed and part 1/3 was still running, so `full-suite-durations` had not written a cache. The only durations cache is still `test-durations-38247246921` (2026-10-12). Of the 8 newest main push smoke runs (40176274138 .. 40182919504) 5 were cancelled, 1 succeeded and 2 were unfinished, and none can have restored a calibrated cache. The balance is therefore not measured and `calibrate_test_durations.py` is unchanged (retune only when max/min is above 1.2). Next step is unchanged: after `full-suite-durations` writes its cache and 3 or more main push runs restore it, run `python tests/tools/ci_part_balance.py --latest 8`.

**Why the first completed nightly still stored nothing (#5133 slice 8), 2026-10-25.** The nightly (run 40179743618) completed green (`suite-plan`, `durations key`, `plan the suite parts`, parts 1-3, `full-suite` all `success`) but `store the suite's durations` was `skipped`, so the newest durations cache is still `test-durations-38247246921` (2026-10-12) and the balance is still not measured. Cause: its condition was `github.event_name == 'schedule' && success()`, and a job-level `success()` is false when any ancestor in the `needs` chain was skipped; the push-only `tested-tree` is skipped on a schedule run and is an ancestor through `full-suite-part` (which uses `!cancelled()` and so ran). Every nightly would have skipped it. The condition is now `!cancelled() && github.event_name == 'schedule' && needs.full-suite-part.result == 'success'` (`test_smoke_test_concurrency.py` evaluates it per event). No other job-level `success()` in `.github/workflows` has a skipped-by-event ancestor. `calibrate_test_durations.py` is unchanged. Next step: after the next nightly stores `test-durations-<run id>` and 3 or more main push runs restore it, run `python tests/tools/ci_part_balance.py --latest 8` and retune only if max/min is above 1.2.

**Re-measuring (#5133 slice 9), 2026-10-25.** Still unmeasured. At 12:33 UTC the newest durations cache is still `test-durations-38247246921` (2026-10-12), and the only completed nightly (run 40179743618, 09:13 UTC) ran before the slice 8 fix and stored nothing. The first nightly that can store `test-durations-<run id>` is 2026-10-26 (~09:13 UTC); main push runs can restore it only after that. `ci_part_balance.py --latest 8` was therefore not run (it would read the old cache) and `calibrate_test_durations.py` is unchanged. Next step: after that nightly stores its cache and 3 or more main push runs restore it, run `python tests/tools/ci_part_balance.py --latest 8` and retune only if max/min is above 1.2.

**Re-measuring (#5133 slice 10), 2026-10-26.** Still unmeasured. At 05:46 UTC the 2026-10-26 nightly had not started (it runs ~09:13 UTC); the newest schedule run is still 40179743618 (2026-10-25, pre-slice-8 fix, stored nothing) and the only durations cache is still `test-durations-38247246921` (2026-10-12), so no main push run can have restored a calibrated cache. `ci_part_balance.py --latest 8` was not run (it would read the old cache) and `calibrate_test_durations.py` is unchanged. Next step: once a nightly stores `test-durations-<run id>` and 3 or more main push runs started after it restore it, run `python tests/tools/ci_part_balance.py --latest 8`, compare with the 8 runs above (max/min 1.24-1.77, median 1.4) and retune only if max/min is above 1.2.

**Measured after the first stored nightly cache (#5133 slice 11), 2026-10-27.** The 2026-10-27 nightly (run 40484179495) stored `test-durations-40484179495` at 10:13 UTC, and every main push smoke run after it ran the restore and balance steps successfully (the log does not say hit or miss). `ci_part_balance.py --latest 8 --event push` read 6 usable runs (40588784432 and 40568489319 unfinished or unsuccessful): max/min 1.75, 1.01, 1.11, 1.04, 1.35, 1.00, median 1.07, 4 of 6 within 1.2, slowest part mean 5.1 min. Before the cache the 8 recorded runs were 1.24-1.77, median 1.4. The suite is now 2 parts (`shard-plan`), not 3, so the figures are for `full-suite part 1/2` and `2/2`. The "about 20%" acceptance is met on the median; two of six runs (1.75, 1.35) stay above 1.2, which one sample cannot tell from runner or queue noise. `calibrate_test_durations.py` is unchanged: retune only if a larger sample keeps the tail above 1.2.

## Test-time ratchet (#5166)
`tests/tools/time_ratchet.py`, baseline `tests/test_time_baseline.json` (the tests over 10 s with their seconds, and `suite_budget_s`). Each full-suite part of `smoke-test.yml` runs with `GITGALAXY_TEST_TIMES` set (`tests/conftest.py` writes every test's seconds plus the reasons of `slow`-marked ones) and then runs `time_ratchet.py check` on it. One timing on a shared runner is +-20-30%, so a hard 10 s edge gave false reds (owner decision 2026-10-15): an unmarked, unbaselined test **fails only over 15 s** (fix it, or `@pytest.mark.slow(reason=...)`, or baseline it), a test between 10 s and 15 s is a **warning** in the job summary, and a baselined test fails over **2.5x** its recorded seconds. Do not add a slow mark to a test that is only near 10 s on a noisy runner. The step is inside the required part, so it always reports. The `suite-time` job (not required) sums the three parts' own seconds and prints the total and its delta against the budget in the job summary; on the nightly it fails over +10%, lists every test over 10 s that has no slow mark or baseline entry (`time_ratchet.py over`), and files or refreshes one issue ("Suite time over budget (nightly)") for both. The only workflow permission added is `issues: write` on that job. `update` only lowers; `pr_gates.py --ratchets` has a `time` entry that checks the committed `.test_durations`.

## ReDoS sweeps on pull requests (#5166)
`tests/conftest.py` marks every test under `tests/extraction/` whose name has `redos` or `linear_on_pathological` as `redos_sweep` (about 750 tests, ~18 of that directory's 19 minutes). The `full-suite` parts of `smoke-test.yml` plan first (`tests/tools/sweep_plan.py`, as `det` and `ground-truth` do): a pull request whose every changed file is a provable non-input (docs, `.claude/`, the other workflows, `tests/cobol_mainframe/`, `tests/equivalence/`, `tests/tools/`) runs pytest with `-m "not golden_crucible and not redos_sweep"`. The list is an allow-list of what the sweeps do not read, so an unlisted file is an input. Pushes to main, the nightly, manual runs, the `shepherd:full` label, an empty or unreadable diff and `full-suite-gate.yml` always run the sweeps. `full-suite` still runs and reports on every PR. The ~23 `core_engine` `*_redos_sweep` tests are not marked. Measured from `.test_durations`: the `tests/extraction` tests the marker names total about 578 s, the unnamed rest of that directory about 75 s (slowest 7.8 s), so no slow extraction test escapes the marker. Engine files the sweeps provably do not import (`ENGINE_NON_INPUTS` in `sweep_plan.py`: `gitgalaxy/tools/cobol_to_java/`, `gitgalaxy/standards/cics/`, `gitgalaxy/tools/terabyte_log_scanning/`, the two COBOL controllers) are no longer sweep inputs either; `test_sweep_plan.py` recomputes the sweeps' import closure and fails if a listed path is in it. `python tests/tools/sweep_plan.py --replay 50` (needs `gh`) plans the last N merged PRs and prints the skip share and the serial minutes saved (each skipped run saves the marked tests' `.test_durations` total, ~576 s). On 2026-10-24 (re-measured later that day, after more engine PRs landed), 23 of the last 50 merged PRs (46%) would have skipped: about 221 serial runner-minutes (~9.6 per skipped run); the earlier sample read 38 of 50 (76%), so the share moves with the PR mix.

On a pull request the `full-suite` parts also skip `tests/cobol_mainframe/` (`PYTEST_ADDOPTS=--ignore=tests/cobol_mainframe`, written by the plan step): `ground-truth` runs that whole directory whenever a ground-truth input changed, and a PR that changed none cannot move it. Push, nightly, manual runs and `full-suite-gate.yml` still run it in the suite.

## Fewer PR jobs (#5132)
PR CI is limited by queueing (a pool of about 20 concurrent jobs), so every job that leaves the PR path frees a slot. Three changes, none touching a required check (required: `det`, `full-suite`, `ground-truth`, `mypy-audit`, `ruff-audit`):

* `gitgalaxy.yml`: Vault Sentinel, X-Ray Inspector and Supply Chain Firewall (59 s, 42 s and 147 s of job time on a recent PR, mostly setup) are the three steps of one `pre-gate` job. A later step runs after an earlier failure (`!cancelled()`), so one push still reports every failing gate. The check name is now `Pre-gate (Vault Sentinel, X-Ray, Supply Chain)`.
* `muninn.yml`, `codeql.yml`: a PR starts them only when `gitgalaxy/**`, `.github/**`, a dependency pin (`pyproject.toml`, `ci/requirements/**`, `templates/requirements/**`, `requirements*.txt`, `action.yml`) changes (Muninn also `.claude/**`). The weekly schedules stay as the backstop for everything else.
* `muninn.yml` on a PR checks out only the filter's paths (sparse, #5499): "Run Muninn" 7 m 28 s -> about 56 s, checkov being 84% of the old step. The sparse list keeps `tests/requirements-mypy.txt` (#6489), the one manifest osv-scanner finds, so osv-scanner scans on PR runs again (run 40118929687, 2026-10-24: "Run Muninn" 68 s, `osv-scanner: 0 finding(s)` in 9 s instead of exiting 128); `test_muninn_scope.py` guards every tracked `*requirements*.txt`. Same-SHA check (#5499): dispatch `muninn.yml` twice with `scope: full` and `scope: pr`, download the two `muninn-sarif-*` artifacts and run `python tests/tools/muninn_scope_diff.py FULL.sarif PR.sarif`; it exits 0 only when the findings inside the PR checkout's paths are equal, and lists the full-scan-only findings by directory.
* `golden-crucible.yml`: a PR starts the two legs only for engine code, the golden fixtures and their helper modules, the crucible pin, dependencies or the workflow itself, minus the COBOL-to-Java translator and its entry point (no scan reads them) and prose: the same exclusion as `crucible-path-independence.yml`. `tests/tools/test_ci_critical_path_split.py` checks the filters against sample changed paths and that every bare module `test_golden_crucible.py` imports is covered. It runs no per-test time ratchet (#5257, decided 2026-10-25): the marker selects two tests that share one module-scoped `galaxyscope` run over the whole crucible, so the scan's 2.5-4 minutes land on whichever test runs first and `time_ratchet.py` would read a shared fixture, not a slow test (#5269). The scan is already bounded by `GOLDEN_SCAN_TIMEOUT` and the job's `timeout-minutes: 30`; the two tests are absent from `.test_durations` (opt-in marker), and the job takes 2.5-4 minutes per leg (runs 40229427427, 40218760491).

| PR type | Jobs before | Jobs after | Job-minutes saved (recent runs) |
|---|---|---|---|
| engine (`gitgalaxy/**`, not translator) | 3 pre-gate + Muninn + CodeQL + 2 golden = 7 | 1 + Muninn + CodeQL + 2 golden = 5 | 2 runners; setup of 2 jobs |
| translator-only | 7 | 1 + Muninn + CodeQL = 3 (Muninn and CodeQL run because the translator is Python under `gitgalaxy/**`) | 2 golden legs (about 7 min) plus 2 pre-gate runners |
| tests / docs / `.claude` only | 7 (docs-only: none of the path-ignored ones) | 1 | Muninn about 7.6 min, CodeQL about 4.9 min, 2 golden legs about 7 min, 2 pre-gate runners |

The critical path (time-to-green) is unchanged on an engine PR: it is `full-suite` and `ground-truth`, set by #5133 / #5151. Runner-minutes are from one recent run of each workflow, not a controlled measurement. The nightly durations cache is recorded under `-n auto` contention and scaled to each part's pytest wall (see #5133 below).
- **Network fetches in a workflow step** (apt, npm, `docker pull`, the corpus clone, hash-pinned `pip install`) go through `tests/tools/ci_retry.sh 4 10 --` so a hiccup is retried and a final failure prints the `INFRASTRUCTURE` marker the shepherd reruns (#5048). `test_ci_retry.py` pins the wrapped sites and caps the workflows still unwrapped.

## Ports Compile: the clean-install check only when packaging can change (#6672)
`ports-compile.yml`'s "Assess clean-install check" (`scripts/check_assess_install.py`, #4726) builds the wheel and runs the installed `gitgalaxy assess` with no network. It was ~3.1 of the job's ~7.9 min (median of 60 PR runs) and never failed in ~420 runs (2026-10-22..25); what only it catches is a packaging break. On a PR it now runs only when `tests/tools/assess_install_plan.py` finds a change that can cause one: packaging or the check itself (`pyproject.toml`, `MANIFEST.in`, the script, the pinned estates), the assess command (`gitgalaxy/cli.py`, `gitgalaxy/tools/readiness/**`), a file added / removed / renamed under `gitgalaxy/`, or a modified data file a `package-data` glob ships. Replayed over the last 80 merged PRs: 4 of the 31 that ran Ports Compile (3 added modules, 1 `pyproject.toml`). Main dispatch and the nightly always run it; an unreadable or short PR file list, or a failed plan, runs it. `publish-assess-check.yml` runs only after a release is on PyPI, so it is not the per-merge backstop: main's dispatch is.
## Equivalence E2E: only what ground-truth cannot run (#6664)
`equivalence-e2e.yml` is not a required check, so its wall time never holds a merge; its cost is the runners it takes from the pool the required checks queue on. Two cuts, measured from the junit of one ground-truth run and one E2E run on the same commit (40225536142, 40225533892): the shards ran 7822 tests and 7126 of them also passed in `ground-truth`. The shards now run only the files whose result can differ (`tests/tools/equivalence_e2e_select.py`: 84 files, all 696 shard-only tests kept), so their test time falls from about 4988 s to 3365 s, and they split 3 ways instead of 4 over measured seconds (`tests/equivalence_e2e_durations.json`). The `db2` job (one runner, ~21 min) runs on a PR only when an input of the five Db2 files changed: a replay of the last 80 merged PRs gives 21 runs instead of 45 (it failed in none of its last 58 PR runs, and `det` re-proves the Db2 det ports). Push, nightly and manual runs run everything, and Main Watch now watches Equivalence E2E. Rules and the durations refresh: `docs/ci_env_gated_tests.md`.


## Smoke suite plan (#6278 item 3)
`suite_select_plan.py` (the classifier's `area()`) plans the `full-suite` on a PR: `skip` (prose nothing opens, `full-suite` reports success), `select` (docs / agent config only: just the tests that read them) or `full`; `shepherd:full` forces full. Push, nightly and dispatch always run the full suite. `push: paths-ignore: docs/**` stays on purpose: a push cannot be planned (the diff is not a PR's), and dropping it would run the full suite on every docs-bot push to main; the PR run already tested those docs.

`python tests/tools/suite_select_plan.py --replay 50` (needs `gh`) plans the last N merged PRs and prints the skip / select / full counts. Measured 2026-10-25 on the last 50 merged PRs: 0 skip, 8 select (16%), 42 full (84%). The suite runs in full for most PRs because most change the engine or `tests/tools`; the select share is the docs / agent-config PRs, each running only its readers instead of the whole suite.

## Smoke on main is queued, not cancelled (#6514)

A main push no longer cancels the previous push's Smoke run (`smoke-test.yml`): under a stream of merges 8 runs in a row were cancelled on 2026-10-24, so main never had a green run and `ci-red-main` could not close. One run goes on and the newest push waits behind it (GitHub keeps one pending run per group). A PR re-push and a manual dispatch still cancel. Cost: a main push run is about 5-6 min per full-suite part (see the #5543 measurement above), now paid for the runs that used to be cancelled early; at most two main runs exist at a time. `java-compile.yml` still cancels main pushes the same way.

## Ground-truth PR check re-measured (2026-10-24, #5543)
The five newest first-attempt successful PR runs of `mainframe-ground-truth.yml` that ran `plan` (runs 40126177113, 40126269812, 40126275997, 40126298574, 40126320956, 19:37-19:40Z). Critical path = run time of `plan` + slowest part + final job, queue left out; runner-min = sum of each job's run time rounded up to the minute.

| run | what ran | critical path | runner-min | wall (queue included) |
|---|---|---|---|---|
| 40126320956 | 2 parts, scans restored from cache | 4.3 min | 10 | 15.7 min |
| 40126177113 | busy: 2 self-warming parts | 8.6 min | 19 | 22.9 min |
| 40126269812 | busy: 2 self-warming parts | 10.5 min | 21 | 22.5 min |
| 40126275997, 40126298574 | `plan` only (no input changed) | 0.4 min | 2 | 3.8-4.5 min |

Against the 7.5 min target: the cache hit and plan-only rows meet it on run time. The two busy-layout runs miss it by 1.1-3.0 min of compute, and every row with parts misses it on wall because each job waited 8-10 min for a runner. In the busy runs each part spent 2.4-3.2 min scanning cold and 3.5-5.6 min in pytest (part 1 also runs the 0.5 min ledger gate). That is a sample of 3 part-running runs, so a gap under a minute is noise. Next cut, not done here: in the busy layout let each part scan only the corpora its pytest share reads (option (b) of #5543); it needs the per-test corpus map and changes the workflow, so it is its own slice.
