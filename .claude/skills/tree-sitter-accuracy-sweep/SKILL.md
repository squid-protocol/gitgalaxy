---
name: tree-sitter-accuracy-sweep
description: Run a Claude-mediated, Gemini-implemented sweep of GitGalaxy's tree-sitter accuracy gaps -- pick the worst-performing languages/metrics from docs/self_scan/tree_sitter_accuracy_history.csv, root-cause each one, file a scoped GitHub issue, dispatch the fix to a Gemini/agy subagent in an isolated worktree, and keep a pool of 4 dispatches active at a time until the backlog thins out. Use when the user asks to "run an accuracy sweep", "find the worst performing languages and fix them", "do another round of gemini fixes", "keep gemini busy on accuracy gaps", or similar recurring tree-sitter-accuracy-audit-driven work. Not for a single hand-picked language fix with no candidate-selection step (just dispatch directly), and not for extraction-gauntlet hardening with no tree-sitter ground truth involved (that's harden-language-extraction).
---

Source of truth for the underlying measurement tool is `tests/tools/tree_sitter_accuracy_audit.py
--help` (read it, it documents corpus/baseline/scope caveats in depth) and epics
`[tree-sitter accuracy epic #1227](https://github.com/squid-protocol/gitgalaxy/issues/1227)` /
`#1261`. This skill is the operational playbook layered on top: how to pick targets, investigate
them, and run a *pool* of parallel Gemini dispatches rather than one at a time. It codifies
lessons from the first two real batches (haskell/ruby/kotlin, then dart/csharp/zig,
2026-08-12/13) -- read this file's steps directly rather than re-deriving the process from
scratch or from memory of a past run.

**Stay in the main conversation for all of this.** Candidate selection, root-cause investigation,
and independent verification all need tight judgment and access to the live regex/corpus --
matching this repo's model-tiering guidance (CLAUDE.md), which reserves regex engineering for the
main session. Only the *implementation* of an already-diagnosed, already-scoped fix goes to a
Gemini/agy subagent.

## 0. Housekeeping before starting a new sweep

- `git fetch origin main && git checkout main && git pull --ff-only` -- work from a current base.
- `git worktree list`, then for any worktree whose branch already has a MERGED PR
  (`gh pr list --head <branch> --state all --json number,state`), `git worktree remove --force`
  and `git branch -D` it. Stale worktrees from a prior batch otherwise just accumulate.
- Confirm `LANGUAGE_CRUCIBLE_PATH` resolves: `ls /home/joe/nyx_projects/language-crucible`. Every
  script invoked from inside a worktree needs this env var passed explicitly -- worktrees are
  NOT siblings of the main repo, so the tool's default `../language-crucible` sibling-resolution
  does not find it from there.

## 1. Pick candidates from the CSV, not by memory of a past table

```bash
source venv/bin/activate  # main checkout's own venv, already has all deps
export LANGUAGE_CRUCIBLE_PATH=/home/joe/nyx_projects/language-crucible
python tests/tools/tree_sitter_accuracy_audit.py --history   # refresh the CSV with live numbers
```
Then read the CSV's latest `timestamp_utc` batch (or just re-read the regenerated summary table
in `gitgalaxy/standards/language_standards.py` between the `TREE_SITTER_ACCURACY_TABLE` markers --
same data, easier to eyeball). Rank languages by their worst non-N/A metric among func
recall/precision and class recall/precision. `N/A` means no tree-sitter grammar / no ground
truth for that metric -- not a candidate, skip it (css/html/groovy/lua/makefile/shell's class
columns, etc.). A metric already at 100.0% across the board for a language means nothing to find
there -- skip it too.

Before adding a language to the candidate queue, `gh issue list --search "<lang> func_start" OR
"<lang> class_start" --state all` to confirm there isn't already an open (or very recently
closed, i.e. a fix in flight) issue for the exact gap you're about to file -- don't duplicate.

Build a candidate queue ordered worst-first. You don't need to investigate the whole queue up
front -- see the pool algorithm in step 4.

## 2. Root-cause each candidate (main session, per language)

This is the expensive, judgment-heavy step -- do not delegate it. For each candidate language:

1. Live-run the audit tool (no `--ci`/`--regenerate` flag, so it prints samples):
   `python tests/tools/tree_sitter_accuracy_audit.py --lang <lang>` and read its "Sample missing"
   / "Sample extra" / "Sample args-count mismatches" output.
2. For a concrete false-positive/false-negative name, grep the actual corpus file
   (`language-crucible/data/<lang>/...`) at that name to see the real surrounding source.
3. If the mechanism isn't obvious from reading the source, run the language's actual compiled
   regex against the file directly and print match spans with line numbers -- this is usually
   the fastest way to see exactly where a match starts/ends and why (see this skill's own commit
   history for the one-off `finditer` script pattern used on #1417/#1418).
4. Form a concrete, evidence-backed hypothesis (not a guess) and a suggested fix shape, ideally
   pointing at an existing precedent already in `language_standards.py`'s comments (`#1221`'s
   Invocation Shield, `#1319`'s bare-`;` modifier-gating, etc.) -- Gemini implements faster and
   more accurately when pointed at this codebase's own established idiom for the bug class,
   rather than left to invent a fresh approach.

## 3. File the issue

One scoped issue per language/mechanism, same shape as #1417/#1418/#1419: Summary (what the
audit measures + the number), confirmed repro with real corpus file/line, suggested fix shape
with a pointer to precedent, explicit out-of-scope notes for anything adjacent you noticed but
didn't chase, and the standard scope note that this only affects extraction-pillar naming
accuracy (epic #813), not risk-scoring. Label `bug,testing,core-engine,threat: false-positive`
or `threat: false-negative` + a priority.

**Any incidental finding surfaced later during verification (step 6) that's outside this issue's
scope gets its OWN new issue too, filed before moving on** -- do not just leave it as a footnote
in the PR description. A PR-body aside is not searchable or triageable by a future sweep; a filed
issue is. (See `file-incidental-findings-as-issues` memory -- this was a real correction, not a
nice-to-have.)

## 4. Set up the worktree + venv (per language, before dispatch)

```bash
git worktree add -b fix/<lang>-<issue#>-<short-slug> \
  ../gitgalaxy-worktrees/fix-<lang>-<issue#> main
cd ../gitgalaxy-worktrees/fix-<lang>-<issue#>
python3 -m venv venv
venv/bin/pip install -q -e ".[yaml]"
venv/bin/pip install -q tree-sitter-language-pack networkx tiktoken pandas numpy xgboost pyyaml \
  pytest ruff mypy
```
**Include `pytest ruff mypy` in that install line.** An earlier batch's prebuild step omitted
them and the Gemini subagent had to improvise (copying `pytest` over from the main venv) --
build the venv complete the first time, since agy's sandbox cannot `pip install` anything itself
(no outbound network at all).

## 5. Grant Gemini/agy access to the new worktree(s)

`~/.gemini/antigravity-cli/settings.json` needs, per worktree:
```json
"read_file(/home/joe/nyx_projects/gitgalaxy-worktrees/fix-<lang>-<issue#>)",
"write_file(/home/joe/nyx_projects/gitgalaxy-worktrees/fix-<lang>-<issue#>)",
```
in `permissions.allow`, plus the same path added to `trustedWorkspaces`. Claude Code's own
permission classifier blocks the assistant from editing this file autonomously (one AI expanding
another AI's unsupervised write access) -- **use `AskUserQuestion` to get an explicit,
specific-to-this-edit approval before editing it** (a general "go ahead" earlier in the
conversation is not enough; a scoped approval via `AskUserQuestion` is what actually lets the
`Edit` tool call through). Batch this: if you're seeding the pool with multiple languages at
once, ask once for the whole batch of new worktree paths rather than once per language.

## 6. Dispatch to Gemini -- and keep a pool of 4 active

Use `Agent` with `subagent_type: gemini-analyzer`, `run_in_background: true`. Each dispatch prompt
must be fully self-contained (the subagent has no memory of this conversation) and MUST include,
every time, not just when convenient:

- The issue number + a `gh issue view` pointer, plus the concrete repro/diagnosis/suggested-fix
  inline (don't make it re-derive what you already found).
- **Exact worktree path, exact branch name.**
- **"A venv is already built at `venv/` with everything needed. Do not `pip install` or attempt
  any network access -- agy's sandbox has no outbound network, every install attempt fails on DNS
  resolution. Use `venv/bin/python`/`venv/bin/pytest` directly."**
- **`LANGUAGE_CRUCIBLE_PATH=/home/joe/nyx_projects/language-crucible` must be passed explicitly**
  to any script that needs the corpus (not a worktree sibling).
- What to verify before returning: the relevant `pytest` files, the live (no-flag)
  `tree_sitter_accuracy_audit.py --lang <lang>` before/after numbers.
- **"Leave changes uncommitted -- do NOT run `git commit`."** Committing from agy's sandbox fails
  (the worktree `.git` points outside any `--add-dir` grant); the outer session commits.
- **"You must actually BLOCK and WAIT for the backgrounded `agy` process to fully exit before
  ending your turn. Do not report 'still running, I'll check back' as a final answer."** This is
  by far the single most common failure mode -- as of the second real batch run (2026-08-13,
  8 dispatches total across two waves), it hit essentially EVERY dispatch at least once, not just
  an occasional one. Expect it as the default first response, not an exception. A subagent
  backgrounds its own `agy -p ...` call and ends its turn reporting the interim "launched, will
  report later" status as if it were the final answer, which fires a premature "completed"
  task-notification. **When you see this happen** (the notification's `<result>` describes
  launching/monitoring rather than an actual diff+numbers+test-result), immediately use
  `SendMessage` back to that same agent (by its agentId) with an explicit "you already did this,
  go check on the real process and block until it exits, do not re-report the same interim
  status" instruction -- this has reliably produced the real completion every time it's been
  tried, so don't hesitate or try a different remedy first. This does not free up a pool slot --
  the dispatch is still active, just not done yet. Budget for one extra round-trip per dispatch
  as normal overhead when estimating how long a pool cycle will take, not as something to
  investigate or fix -- it hasn't blocked any dispatch from eventually completing correctly.
- **"If you hit a permission/sandbox wall you can't get past, STOP and report the exact error.
  Do NOT attempt `--dangerously-skip-permissions`, and do NOT edit `settings.json` or any other
  config file to route around it, regardless of what the tool's own error message suggests."**
  (A subagent self-escalating agy's permissions has happened once before -- see
  `gemini-agy-integration` memory.)

**Pool mechanics**: maintain a queue of investigated-and-issue-filed candidates (from steps 1-3)
and a set of currently-active dispatches, target size 4. Whenever a dispatch's task-notification
represents a genuine completion (not the premature-interim-report false completion above):
1. Independently verify it (step 7) and open its PR (step 8) -- don't skip this to rush the next
   dispatch out; a bad fix merged is worse than a slow queue.
2. Immediately backfill: if the investigated-and-issue-filed queue has a language ready, set up
   its worktree/venv/permissions (steps 4-5) and dispatch it (step 6) to bring the active count
   back to 4. If the queue is empty but the CSV-derived candidate list (step 1) still has
   uninvestigated languages, root-cause and file the next one now (steps 2-3) before dispatching,
   rather than leaving a slot idle.
3. If both are empty, let the pool shrink below 4 -- that's the sweep winding down, not a bug to
   fix.

Use `ListAgents` if you lose track of which dispatches are still active vs. already resolved.

## 7. Independently verify every fix before it gets committed

Never trust a subagent's (Gemini's, or the dispatching Claude subagent's) own "verified, all
green" self-report as sufficient on its own -- re-run things yourself:

1. `git diff` in the worktree -- read the actual regex change. Confirm it matches the suggested
   fix shape from step 2/3, is commented in this codebase's established style, and doesn't touch
   anything outside its stated scope.
2. Sanity-check for reintroduced ReDoS if any quantifier changed (quick pathological-input timing
   probe, or just re-run the language's own `test_<lang>_strict.py` ReDoS harness).
3. Re-run the exact `pytest` command yourself; don't just read the subagent's claimed output.
4. Re-run `LANGUAGE_CRUCIBLE_PATH=... venv/bin/python tests/tools/tree_sitter_accuracy_audit.py
   --lang <lang> --regenerate` (writes `tests/tree_sitter_accuracy_baseline_<lang>.json`) then
   `--summary-table` (updates `language_standards.py`'s docstring table). Confirm the numbers
   moved the direction the issue predicted.
5. **File a new issue for anything you notice along the way that's outside the current issue's
   scope** (see step 3's note) -- don't just mention it in the PR body.

## 8. The full "done" bar -- bundle this as one sequence, every time

A fix isn't ready to push after "tests pass." Missing any of these has caused real live-CI
failures on a merged PR before:

```bash
export PATH="$PWD/venv/bin:$PATH"
export LANGUAGE_CRUCIBLE_PATH=/home/joe/nyx_projects/language-crucible
python tests/tools/tree_sitter_accuracy_audit.py --lang <lang> --regenerate  # bless the target's own baseline
python tests/tools/tree_sitter_accuracy_audit.py --all --ci                # see below -- not optional
python tests/tools/tree_sitter_accuracy_audit.py --summary-table
python tests/tools/crucible_check.py --mode both              # see the drift first
python tests/tools/crucible_check.py --mode both --update --yes   # bless if drift is expected
python tests/tools/crucible_check.py --mode both              # re-run, confirm now PASS/PASS
python tests/tools/audit_check.py --ci                         # ruff+mypy+dead-key+ast-accuracy
```
`crucible_check.py` handles the two-venv (`.crucible_venvs/{full_precision,zero_dependency}`)
dance itself now -- don't hand-build those venvs. Expect real cascading drift in the golden
masters beyond just the target language's own directory (global PageRank/spatial-coordinate
stats shift slightly for the whole corpus when any one language's function count changes) --
that's expected, not a sign something's wrong; bless it and move on. `audit_check.py --ci` is
authoritative for the ruff-format-clean verdict -- don't trust an ad hoc direct `ruff format
--check` run with whatever `ruff` version happens to be on PATH, it can disagree in ways that
don't matter.

**`--all --ci` is not optional whenever a fix touches a SHARED helper** (anything in `detector.py`
or `prism.py` outside a `lang_id == "<target>"` gate -- e.g. `_extract_name()`, `fast_shield()`,
the generic string/comment-shielding passes). A real incident (#1419's zig PR, 2026-08-13):
widening `_extract_name()`'s word-tokenization character class to support zig's `@"..."` quoted
identifiers also silently changed CSS's `@media`/`@import` at-rule name extraction (`@media` ->
`media`), since the class change wasn't actually gated to zig at all. The full repo test suite
passed clean (6851 tests, no CSS-specific case exercised the exact regression shape) and targeted
spot-checks of a few "likely affected" languages (csharp, cpp, rust, scala -- picked by guessing
which languages might collide, not by checking all of them) also passed clean. Only
`tree_sitter_accuracy_audit.py --all --ci` -- which diffs literally every baselined language's
real-world corpus numbers, not just the target's -- caught it, and only because CI ran it after
push; it hadn't been run locally before that push. **Run `--all --ci` locally before every push
that touches a shared helper, not just the target language's own `--lang <lang> --ci`** -- a
green target-language result and a green general test suite are both necessary but neither is
sufficient on its own to rule out cross-language ripple from a shared-function change.

Commit everything the regenerate/update steps touched (the regex file, the test file, the
per-language baseline JSON, both golden master JSONs), push, `gh pr create`.

**Auto-merge is pre-authorized specifically for this skill's PRs** (user, 2026-08-13): once a fix
has been through the full independent-verification + done-bar checklist above (steps 7-8) and its
own CI is green, merge it -- `gh pr merge <PR> --squash --auto` (let CI gate it rather than force
immediate admin-merge) is fine without asking each time. This is narrower than this repo's normal
CLAUDE.md default (PR creation is pre-authorized repo-wide, merging is not) -- **the broader
default still applies to every other kind of PR**; this carve-out is specifically for fixes
produced by this skill's own root-cause-then-Gemini-implements-then-independently-verify pipeline,
not a general license to merge anything. If a fix's verification turned up something ambiguous
(a judgment call the checklist didn't cleanly resolve, unexpectedly large/unexplained drift, a
test that had to be loosened rather than the code fixed), stop and ask instead of merging through
it -- the pre-authorization covers the routine case, not "trust it because it's from this skill."

## Running this indefinitely (pool of 4, no fixed batch size)

When asked to run this as an ongoing sweep rather than a one-off batch: keep the dispatch pool at
4 continuously -- every time a fix's PR merges, immediately root-cause + file + dispatch the next
worst-performing candidate from the CSV to refill the slot (step 1-6), and keep going indefinitely
until the user says stop. There is no natural "done" state to wait for -- the CSV always has a
next-worst language as long as any non-N/A metric is below 100%, so this only ends when told to.
Re-run `--history` periodically (e.g. once per full pool-refill cycle, not on every single slot)
to pick up fixes' own downstream effects on the ranking rather than working off a stale snapshot
the whole time.

## Known gotchas checklist (recap, all confirmed at least once)

- agy's sandbox has zero outbound network -- prebuild every dependency into the worktree venv
  first, including `pytest`/`ruff`/`mypy`, or the dispatch fails or has to improvise mid-task.
- Subagents background `agy` then report the interim status as final -- watch for this in every
  task-notification, resend an explicit "block and wait" instruction when it happens.
- `git commit` cannot run inside a worktree from agy's sandbox -- the outer session always does
  the commit.
- Never let a subagent self-escalate agy's permissions or edit its `settings.json` to route
  around a wall -- it stops and reports instead, every time, by explicit instruction.
- `LANGUAGE_CRUCIBLE_PATH` must be passed explicitly from a worktree -- sibling-directory
  resolution only works from the main checkout.
- Parallel-PR merge conflicts on the machine-generated files (`golden_master*.json`,
  `ruff_audit_baseline.json`, `tree_sitter_accuracy_baseline_*.json`) are a real, expected,
  survivable cost of running a pool of 4 -- when one lands, `git merge origin/main` on the others,
  take origin/main's version of the conflicting generated files wholesale
  (`git checkout --theirs -- <path>`), then regenerate everything fresh on the merged code and
  re-run the full step-8 checklist again rather than hand-resolving JSON conflicts.
- Editing `~/.gemini/antigravity-cli/settings.json` needs a specific, in-the-moment
  `AskUserQuestion` approval each time new worktree paths are added -- a general earlier "go
  ahead" doesn't carry forward.
