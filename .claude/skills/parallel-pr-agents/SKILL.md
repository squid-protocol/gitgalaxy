---
name: parallel-pr-agents
description: Run several subagents in parallel, each landing its own PR against main, without them colliding on worktrees, shared files, or golden masters. Use when the user says "spin up agents for these issues", "work these in parallel", "fan out this roadmap/epic across agents", or is orchestrating several fact-channel/rule-fix/rebase PRs at once (the #3249/#3387 pattern). Covers both what each subagent must do (worktree, commit/PR conventions, additive-only edits, own-drift re-blessing, scratch files, CI watch, report format) and what the orchestrator must do (model tiering, concurrency cap, merge-train order, rebase-after-merge, a background PR-queue monitor, verifying claims) and fleet operations (lock tiers, freshness, shared-venv hygiene, stop-cleanup, PID watchers, WIP checkpoints, golden merge trains, load-aware bless, the `gitgalaxy-pr-worker` agent and `tests/tools/box/` tools). NOT for a single agent working one issue alone (no orchestration concerns), and not a substitute for `add-fact-channel`'s own per-channel spine/checklist.
---

Lessons from the #3249 round (PRs #3349, #3350, #3357, #3368, #3369, #3375) and the #3383-#3387
follow-up: parallel agents on this repo fail in specific, repeatable ways — shared-seam conflicts,
a rate-limit cascade, a merge landing while a sibling was still rebased on the old main, an agent's
self-reported "done" that CI actually disagreed with. This skill is the checklist that prevents
each one recurring, not a general parallel-agent tutorial.

## For each subagent

- **Its own worktree, off `origin/main`, never the main checkout.** Spawn from the launcher, not
  from inside another agent's worktree:
  ```sh
  git fetch origin
  git worktree add ../gitgalaxy-worktrees/<branch-slug> -b <type>/<issue>-<slug> origin/main
  ```
  Mirrors `tests/tools/worktree_env.sh`'s own rule: refuse to run against the primary checkout, and
  never share a worktree directory between two agents.
- **CLAUDE.md's commit/PR conventions, exactly.** Commit only files relevant to the change (never a
  broad `git add -A`); verify `main..HEAD` doesn't carry unrelated in-progress work; end commit
  messages and PR bodies with the attribution lines the launching session was given. Never merge,
  never force-push (plain `--force`), and never run another destructive/irreversible git operation
  (`reset --hard`, `--no-verify`, rewriting published history) without explicit confirmation — PR
  creation and commits to a feature branch are the only pre-authorized actions.
- **Additive-only edits to shared seams.** Every #3249-round PR touched the same files (`galaxy_ir.py`
  SCOPE + accessors, `refraction_differential.py`, `cobol_answer_key.py`, `record_keeper.py`,
  `state_rehydrator.py`, `audit_recorder.py`/`llm_recorder.py`, both golden masters, the ruff
  baseline). Add a new block/key/row in one place; never restructure or reorder something a sibling
  PR also touches — a reorder turns a clean rebase into a manual conflict for everyone still in
  flight.
- **Re-bless only your own drift.** After regenerating golden masters or the ruff baseline, diff
  against main and confirm every changed entry is yours (plus the expected topological X/Y/Z
  ripple). Re-blessing a sibling's already-merged drift silently reverts their work — see
  `add-fact-channel`'s rebase/re-bless section for the full procedure `tests/tools/
  rebase_rebless.py` (#3385, in progress) will eventually automate.
- **Scratch files go in `/tmp/gitgalaxy-scratch/claude/`** (or the harness-provided per-session
  scratchpad directory), never the repo tree, not even temporarily — see CLAUDE.md's "Scratch files
  & working directory" (#1091: ~130 stray files had to be purged twice).
- **No `jq` in shell loops.** `jq` is unavailable in the unsandboxed shell an agent's CI-watch loop
  runs in; a loop built around it never finishes. Use `gh -q` (`gh`'s own `--jq`/Go-template flag)
  or `grep`/`awk` instead.
- **Watch CI once**, after pushing — `gh pr checks <pr> --watch` (or a single poll loop, not a
  babysitting loop that never exits) — and report what it actually said, not an assumption that it
  will pass.
- **A final report under 200 words**, handed back to the orchestrator: PR URL, the design decision
  (which table/shape/approach and why, one line), the evidence actually gathered (real scan output,
  not "should work"), CI status as last observed, and anything left unresolved (a sibling conflict
  not yet rebased, a check still pending, a scoping question). Prefer under-explaining with a
  pointer to the PR body over padding the report — the PR body carries the full evidence template.

## For the orchestrator

- **Model tiering:** Opus for a new channel or any design call (shape decision, table layout,
  which existing seam to extend vs. add to); Sonnet for rule fixes, mechanical rebases, and
  re-blessing. Don't default everything to Opus "to be safe" — most of the round's work is
  mechanical once the design is picked.
- **At most three Opus agents running at once.** A fourth concurrent Opus agent hit the rate limit
  and stopped all three *already-running* agents mid-task, not just the fourth — the failure mode
  is shared, not isolated to the agent that tripped it. Queue the fourth design task behind a slot
  freeing up rather than launching it alongside three others.
- **State the merge-train order up front**, before any agent starts, not after PRs are ready — pick
  it from dependency direction (a channel that another PR's join builds on merges first) and tell
  every agent its position, so a later agent in the chain knows to expect a rebase rather than being
  surprised by one.
- **Rebase after each merge in the train** (via `rebase_rebless.py` once #3385 lands; by hand
  per `add-fact-channel`'s procedure until then) — don't batch rebases and don't let an agent
  discover mid-review that three siblings merged underneath it.
- **Run a background monitor on the PR queue** instead of relying on the user to relay "PR X merged,
  go rebase" — poll `gh pr list`/`gh pr view` state changes and trigger the next agent's rebase
  automatically. This is what turns a stated merge-train order into something that actually executes
  in order without a human in the loop for every hop.
- **Verify agents' claims before reporting them onward.** An agent's final report describes what it
  intended and believes happened, not a guarantee. Before relaying "PR #NNNN is green and ready,"
  run `gh pr view <n>` and `gh pr checks <n>` yourself and report what CI actually shows.

## Fleet operations

Evidence is the 2026-10-03 multi-agent day; each rule below prevents one thing that went wrong.

**Box tools** (`tests/tools/box/`, bash, usage in each header; lock dir `${GG_LOCK_DIR:-/tmp/gitgalaxy-scratch/locks}`):

| Tool | Use |
|---|---|
| `heavy-run.sh <cmd...>` | N shared slots, `N=${GG_HEAVY_SLOTS:-nproc/4}` (min 1). Wrap pr_gates, scans, full suite. |
| `golden-lock.sh <cmd...>` | Exclusive. Golden bless/check ONLY (`crucible_check.py`). |
| `kill-by-cwd.sh <dir> [--dry-run]` | Kill processes whose cwd is under a worktree; lists first; never itself/ancestors. |
| `wait-pids.sh <pid...>` | Block until PIDs exit; prints statuses. |

**Before launch (orchestrator)**
- [ ] Lock tiers decided and stated in every brief: heavy work -> `heavy-run.sh`, golden -> `golden-lock.sh`, slot count fixed. NEVER change lock policy mid-run: one exclusive lock serialized 10+ jobs behind a 40-min proof sweep while 11/12 cores idled, and an agent that changed the policy mid-run was blocked by the auto-mode classifier ("Interfere With Workloads").
- [ ] Brief = issue(s) + acceptance criteria + model + coordination notes only; the setup/run/never boilerplate lives in `.claude/agents/gitgalaxy-pr-worker.md` (launch with `subagent_type: gitgalaxy-pr-worker`). Example:
  `Land #4301 (acceptance: X passes, no golden drift outside rust). Model: sonnet. Merge-train: you are 2nd; #4299 merges first, expect a rebase.`
- [ ] Merge train for golden-touching PRs: order stated up front, golden/pin-bump PRs LAST, each rebased and re-blessed (own drift only) after the one before it merges.
- [ ] Cap concurrent agents so a usage-limit cutoff cannot take the fleet at once (it killed 4 agents together; only the one that had pushed WIP lost nothing).

**During the run**
- [ ] Freshness: `git fetch origin` and re-test on CURRENT origin/main before calling any failure "pre-existing" (agents did so against a main 10 min stale, before #4220). `python tests/tools/pr_gates.py --vs-main` does it and labels each failure "caused by branch" / "pre-existing on main@<sha>".
- [ ] Never mutate a shared venv (an agent pip-upgraded `~/venvs/galaxy_venv` mid-flight). Need another tool version -> private venv under `/tmp/gitgalaxy-scratch/claude/<slug>/`. Match CI's pins: local mypy passed while CI failed ("Cannot infer type of lambda", #4257). `pr_gates.py` now warns on mypy/ruff/python drift from the workflows and prints the private-venv command.
- [ ] Catch what CodeQL catches before push (implicit string concat in a list #4241; missing superclass `__init__` #4236): ruff now selects ISC001/002/004 (baseline-gated); no ruff rule exists for missing `super().__init__()`, so re-read every new subclass by hand.
- [ ] Watchers wait on PIDs (`wait-pids.sh`), never on output files: a watcher hung on files a never-started job would have written.
- [ ] Checkpoint: push the branch and open a placeholder PR (title `WIP: ...`) early; unpushed work dies with the agent.
- [ ] Load-aware bless: a bless/check run under load can time out regexes, which fakes diffs (2,911 golden diffs, #4247). Run it under `golden-lock.sh`, and REFUSE to bless if any file was excluded by a timeout in the run output.
- [ ] Bless ONLY with `golden-lock.sh python tests/tools/crucible_check.py --update --yes` (builds CI-matched venvs per leg). Never run `update_golden_master` from `~/venvs/galaxy_venv` (Python 3.12 vs CI's pin): that produced ~2.9k phantom full-leg diffs on #4258.
- [ ] After any sibling merge that touches golden masters (e.g. #4240 added snapshot section 12), merge origin/main and re-bless; that is what broke #4258's zero-dep leg.
- [ ] After ANY sibling merge, re-validate every claim in the PR body (counts, "no drift", "rebased on") and edit it via `gh api -X PATCH repos/squid-protocol/gitgalaxy/pulls/<n> -f body=...` (`gh pr edit` fails on gh 2.45).

**Stopping an agent**
- [ ] Stop the agent AND its helper subagents, then `kill-by-cwd.sh /nvme-data/projects/gitgalaxy-worktrees/<slug> --dry-run`, review, run without `--dry-run`: stopping an agent left its helper subagent and its queued flock'd pr_gates running. Never `pkill -f <pattern>`: it matched and killed the caller's own shell (exit 144).
