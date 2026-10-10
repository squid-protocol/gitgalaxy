---
name: engine-bugfix
description: Fix one GitGalaxy engine bug (COBOL / mainframe extraction, detector, galaxy_ir readers -- engine code under gitgalaxy/, not the forge) end to end, or integrate several finished fixes as one "train" (one golden regen, one ledger update, one CI run). Covers reproduce-first, the narrowest root-cause fix, regression tests, `tests/tools/bugfix_kit.py` (parallel two-leg golden bless, ground-truth ledger, estate-crucible horror scorecard, audits, PR-body evidence, train attribution), the golden/ledger rules, draft-PR and CI-polling discipline. Use when the user says "fix #NNNN" for an engine defect, "bless the goldens", "run the estate horrors", "write the PR evidence", or "run a train / batch these fixes". Not for the forge (gitgalaxy/tools/cobol_to_java, cobol_to_cobol -- see cobol-modernization), adding a language (add-language) or a signal contract sweep (rule-contract-audit).
---

The kit (`tests/tools/bugfix_kit.py`) runs every check below with the right environment and
logs to files; this skill is the judgement around it. Run `python tests/tools/bugfix_kit.py
--help` for the flags. Every command takes the **worktree** to act on, and always uses that
worktree's own tools and engine.

## 0. Environment

This skill is the bug-fix *loop*; the validation gauntlet itself is `ci-push-checklist` --
follow it for anything it covers that the kit does not (tri-comparison / tree-sitter
baselines when a fix touches another language's rules, the clean-working-tree rule, etc.).
The kit wraps the repo's own tools rather than replacing them:

| kit step | wraps |
|---|---|
| `bless`  | `crucible_check.py --mode full|zero --update --yes`, then `crucible_check.py --mode ...` (both legs as two concurrent processes) |
| `scope`  | `scope_check.py --expect <langs>` (language-bucketed diff vs origin/main) |
| `ledger` | `mainframe_corpus.py fetch`, `ground_truth_ledger.py update` + `check` |
| `estate` | `estate_crucible.py --json` for the base (cached per main commit) and the worktree |
| `audit`  | `tests/{mypy,ruff,dead_key}_audit.py --ci` + the test files you changed |

```bash
python tests/tools/bugfix_kit.py setup <worktree>
```

- Golden venvs are crucible_check's own, per worktree (`.crucible_venvs/`, built on the
  first bless, a few minutes; reused after). The kit adds one language-crucible clone per
  leg at the worktree's `PINNED_TAG` under the kit home (`<main checkout>/../bugfix-kit-home`,
  no `tmp`-like path component), scrubbed before every scan, so the two legs never share a tree.
- `ledger` / `estate` / `audit` use two kit venvs mirroring their workflows (created on first
  use; `BUGFIX_KIT_VENV_LEDGER` / `_AUDIT` to point elsewhere). An existing venv that does not
  match is an error, never silently reinstalled -- `--recreate` rebuilds it.
- `.mainframe_corpora` is symlinked from the main checkout and added to the repo's
  `info/exclude` (the `.gitignore` entry only matches a directory). Never commit the symlink.

## 1. One fix

1. **Worktree from origin/main**, branch `fix/<issue>-<slug>`:
   `git worktree add -b fix/NNNN-x ../gitgalaxy-worktrees/NNNN origin/main`.
   Read the issue with `gh api repos/squid-protocol/gitgalaxy/issues/NNNN` (`gh issue view`
   and `gh pr edit` fail on this org's project cards -- use `gh api` for both).
2. **Reproduce first.** A failing test or a one-file `galaxyscope <path> --db-only --output
   <scratch>` showing the wrong fact, before touching code. If it does not reproduce on main,
   say so on the issue and stop.
3. **Narrowest root-cause fix**, in engine code only. Not `gitgalaxy/tools/cobol_to_java`,
   not the estate-crucible repo, not a corpus. Fix the layer that produces the wrong fact,
   not a consumer that papers over it.
4. **Regression tests shaped like the acceptance criteria**: one test per criterion in the
   issue (the exact input shape it names -- a copybook, a continuation line, a GO TO DEPENDING),
   plus the nearest negative (what must NOT change). Put them next to the existing tests for
   that extractor (tests/cobol_mainframe, tests/extraction, tests/core_engine).
5. **Run the kit** -- one command does all of it:

   ```bash
   python tests/tools/bugfix_kit.py all <worktree>          # setup, bless, ledger, estate, audit, evidence
   ```

   (add `--expect cobol` to also run the `scope` step) or the steps alone: `bless` (both
   crucible_check legs in parallel, update then check),
   `ledger` (fetch + update + check), `estate` (horror scorecard base vs worktree; the base
   side is cached per main commit), `audit` (mypy/ruff/dead-key `--ci`, plus the test files you
   changed, or `-k EXPR` / paths), `evidence` (PR-body markdown). Logs:
   `<kit home>/runs/<worktree>/latest/`.
6. **Read the golden summary before committing** (`evidence` groups it by channel and file).
   Every moved channel must be explained by the fix. See the rules below.
7. Commit the engine change, tests, regenerated fixtures and the ledger together. Push,
   open a **draft** PR (section 4), poll CI (section 5).

Full local suites (tests/extraction, tests/core_engine, tests/cobol_mainframe) are optional
-- CI runs them -- but run the files nearest the change (`audit` does that by default).
A fix that touches another language's rules also owes the tri-comparison / tree-sitter
baselines: follow `ci-push-checklist` for those (the kit does not run them).

## 2. Golden-master and ledger rules

- **Unexplained golden change = stop.** If a channel or file moved that the fix does not
  explain, find out why before blessing it in. Never re-bless to make a failure go away.
- **Bless only through the kit / `crucible_check.py --update`** (per `ci-push-checklist`),
  never by copying output, never from the repo `.venv`, never against an off-pin corpus.
- If `bless` passes the update but the post-bless `golden_crucible` check fails, the scan is
  not deterministic (or the leg's environment is wrong) -- that is a finding, not a retry.
- **Never hand-merge** `tests/golden_master_*` or `ground_truth_ledger.json`. On a conflict:
  `git checkout origin/main -- <those paths>`, then re-run `bless` / `ledger` on the merged tree.
- `ledger check` fails on new `UNTRIAGED` entries: assign each one a cause with
  `ground_truth_ledger.py assign` (an existing cause, or a new one owned by an issue). A
  `defect` cause needs the issue that will fix it; do not mark a defect `deliberate`.
- Estate-crucible is evidence, not yet a gate: report every horror whose verdict moved,
  both directions. A horror the fix should pass that still fails is a finding against the
  engine OR the key -- read both.

## 3. A train (several fixes, one regen, one CI run)

```bash
python tests/tools/bugfix_kit.py train ../gitgalaxy-worktrees/train-1 fix/NNNN-a fix/MMMM-b ...
```

Creates the worktree off `--base` (default origin/main) on branch `train/<dir>`, merges the
branches one at a time (`--no-ff`), and after **each** merge re-scans the full-precision
golden leg and diffs it against the previous step (plus the estate scorecard, and the ledger
with `--ledger-per-step`). Then one `all` on the tip. The evidence gains a **Per-fix
attribution** table: which channels, files and horrors each merge moved on its own.

**Picking a train.** Fixes whose code areas are disjoint (different extractor modules or
different channels -- e.g. a copybook-resolution fix and a JCL DD fix), each already
reproduced, fixed, tested and audited on its own branch. Fix branches do not need their own
bless -- the train regenerates. Keep a fix out of the train if it changes shared scoring
(topology / risk equations: moves every file) or is still in review. 2-5 fixes per train.

**Conflicts.** Conflicts confined to generated artifacts (golden fixtures, ledger) resolve to
the train side automatically (regenerated at the end). Any other conflict aborts that merge
and stops the train (`--skip-conflicting` drops it and continues) -- such fixes are not
disjoint; ship them separately or rebase one on the other.

**Attribution rules.** Each step's delta must be explained by THAT fix alone. A channel that
moves in a step whose fix does not touch it means the fixes interact: stop, and ship the
interacting fix separately. Re-running `train` with more branches appends to the same train.

**Bisecting a failing train.** (1) Golden/estate surprises: the attribution table names the
step. (2) A CI test failure: `git bisect start HEAD <base> --first-parent` on the train
branch, run the failing test per step -- only merge commits are visited. (3) Then drop the
culprit: start a fresh train worktree with the other branches (cheap: scans of already-seen
commits are cached for the ledger and estate).

**PR for a train**: one draft PR from `train/<dir>`, title `fix: train -- #A, #B, #C`,
body = per-fix sections (what was broken / fix / before -> after, per issue) + the kit's
evidence (goldens, per-fix attribution, ledger, estate) + `Closes #A`, `Closes #B` lines.

## 4. PR body (one fix)

`python tests/tools/bugfix_kit.py evidence <worktree> --template --out /tmp/body.md`
fills the measured parts; you write the rest:

```markdown
## What was broken      -- the reproduction: input, what the engine emitted, what it should
## Fix                  -- the root cause and why this layer
## Before -> after      -- the repro and the regression tests, before and after
## Golden masters       -- (kit) per leg: channels / files / leaves moved, newly (un)parsed files
## Ground-truth ledger  -- (kit) fixed / introduced mismatches, scoreboard cells
## Estate-crucible      -- (kit) horrors passing before -> after, each moved horror
Closes #NNNN
```

Every golden channel listed must have a sentence in "Fix" or "Before -> after" saying why
it moved (the small-audits golden-master step expects it).

## 5. Push, PR, CI

- `gh pr create --draft` **only**. A non-draft PR on this repo has been auto-merged within
  seconds, before `mypy-audit` / `ruff-audit` (pull_request-only) could gate it. Never mark
  ready or merge unless the user asks.
- Run `audit` before every push (ruff pinned 0.16.0; keys-only baselines).
- Poll CI with **bounded foreground** polls: `gh pr checks <N>` then
  `for i in $(seq 1 12); do sleep 120; gh pr checks <N> | grep -q pending || break; done`.
  Never background `gh pr checks --watch`: it gets killed here, and a killed watcher is not a
  CI failure -- re-check with a plain `gh pr checks <N>`. Budget ~25 min for the full board.
- A red check: read its log (`gh run view <id> --log-failed | tail -80`), fix forward on the
  same branch. A crucible leg red with a diff = an unblessed or non-deterministic change.
- Use `gh api` for issue / PR reads and edits, e.g.
  `gh api -X PATCH repos/squid-protocol/gitgalaxy/pulls/N -F body=@body.md`.

## Boundaries

Engine code (gitgalaxy/ minus gitgalaxy/tools/cobol_to_java), its tests and generated
fixtures. Never edit the estate-crucible or language-crucible checkouts (the kit's corpus
clones are its own scratch). Commits end with the session's attribution trailer.
