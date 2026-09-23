---
name: parallel-pr-agents
description: Run several subagents in parallel, each landing its own PR against main, without them colliding on worktrees, shared files, or golden masters. Use when the user says "spin up agents for these issues", "work these in parallel", "fan out this roadmap/epic across agents", or is orchestrating several fact-channel/rule-fix/rebase PRs at once (the #3249/#3387 pattern). Covers both what each subagent must do (worktree, commit/PR conventions, additive-only edits, own-drift re-blessing, scratch files, CI watch, report format) and what the orchestrator must do (model tiering, concurrency cap, merge-train order, rebase-after-merge, a background PR-queue monitor, verifying claims). NOT for a single agent working one issue alone (no orchestration concerns), and not a substitute for `add-fact-channel`'s own per-channel spine/checklist.
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
