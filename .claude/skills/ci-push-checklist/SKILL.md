---
name: ci-push-checklist
description: The required CI validation gauntlet for shipping a code fix to GitGalaxy's core engine (language_standards.py, detector.py, prism.py). Use when preparing to push an issue fix, generating a PR, or validating any change to core parsing logic.
---

When shipping a code fix or addressing a discrepancy in GitGalaxy, the following full validation chain MUST be executed before opening the PR. This ensures parsing accuracy is preserved and data-driven artifacts are synchronized. Rough time budget per section is noted -- most of this is I/O-bound (venv builds, corpus scans) and safe to background while you do something else, not something to babysit synchronously.

## -1. Orient before reading code cold (~1 min)
Before grepping or opening a file to gauge "how big/risky is this," check GitGalaxy's own self-scan of itself first -- it exists specifically to make this near-zero-token:
* **`docs/gitgalaxy_architecture_brief.md`** -- repo-wide blast-radius/risk framing (auto-committed on every merge to main, so it's always close to current HEAD).
* **`docs/self_scan/gitgalaxy_master.db`** (SQLite) -- targeted per-file/function complexity queries. Regenerate with `python tests/tools/self_scan.py` if missing/stale (gitignored on purpose). See the `self-scan-query` skill for query patterns.
See CLAUDE.md's "Using GitGalaxy's self-scan output for orientation" section for the full detail (query examples, full-precision dependency requirements) -- not repeated here.

## 0. Clean Working Directory
* **Untracked Files:** Before committing, ALWAYS run `git status` and review untracked files. Do not use `git add .` blindly. Accidentally committing local virtual environments (e.g. `venv/`, `venv_zero/`) or temporary Python scratch scripts will immediately trigger pipeline failures from the X-Ray Inspector (flagging checked-in binaries) or CodeQL (flagging dirty script code).
* **Explicit Adds:** Prefer `git add <file>` for specific files.

## 1. Local & Unit Validation (~1 min)
* **Standalone Regex Re-test:** Isolate the target regex (e.g., `func_start`) against the failing corpus file manually to ensure false positives and negatives are resolved without affecting real matches.
* **See what the engine actually extracted before re-deriving it from source:** `galaxyscope <path> --db-only --debug --output <scratch-dir>` and grep the log for `[WORKER-TRACE] extracted functions for` -- one line per file with the exact satellite/function names produced. Much cheaper than tracing `_slice_by_keywords`/`_slice_by_terminator`/etc. cold when the question is "what did the engine actually name/count here." See CLAUDE.md's "Debugging what detector.py actually extracted from a specific file" for the full recipe (DB cross-reference, etc.) -- not repeated here.
* **Extraction Gauntlet & Strict Tests:** Run `pytest tests/extraction/languages/test_<lang>.py` and `test_<lang>_strict.py` for the language you modified.

## 2. Static Analysis & Linting (~15s)
* **Ruff Formatting & Linting:** `python tests/ruff_audit.py --ci`
* **Mypy Type Checking:** `python tests/mypy_audit.py --ci`

## 3. Global Golden Master Verification (~2-5 min, first run of a fresh venv adds ~30-60s)
* **Run the Crucible Check (Mandatory):** Execute `python tests/tools/crucible_check.py` against the full ~80-repo corpus.
* **Re-Bless Golden Masters:** If `crucible_check.py` shows expected, accurately traced diffs resulting from your fix, bless the new state:
  `python tests/tools/crucible_check.py --update --yes`
  * Always go through `crucible_check.py --update`, never `python tests/tools/update_golden_master.py`
    directly -- the latter only updates whichever ONE fixture matches whatever happens to be
    importable in your current shell, with no automatic venv/PATH management; `crucible_check.py
    --update` runs it once per mode through its own properly-scoped venv, no manual bookkeeping.
  * **Claude Code note:** blessing a golden master is exactly the kind of action Auto Mode's
    classifier treats as destructive-looking and blocks by default (even via `--yes`, even on a
    clean tree where it would be a no-op) -- expect to explicitly ask the user for one-time
    permission before this step rather than being surprised mid-task.
* **Isolate exactly what your change touched, independent of whether the committed fixture is even current:** `python tests/tools/scope_check.py --expect <lang>[,<lang2>]` scans your working tree AND a comparison ref (default `origin/main`) fresh, in separate venvs, and buckets every difference by language -- fails loudly if anything outside `--expect` changed. This answers "is my diff actually scoped to what I meant to touch" directly, without needing the committed golden master to be current first (useful mid-investigation, or after `main` has moved and the committed fixture reflects a bunch of OTHER PRs' legitimate changes you didn't make). Costs roughly 2x a single `crucible_check.py` run (it builds and scans two venvs, not one) -- background it.
* **On the old "never clone a fresh corpus copy" folklore:** a fresh `language-crucible` clone is fine, and both `crucible_check.py` and `scope_check.py` do this routinely (the latter clones a temporary comparison-ref worktree every run). What actually causes massive, invalid-looking diffs is one of two SPECIFIC, now-automatically-checked things, not "metadata" in general (verified by direct repro, PR #2518, 2026-08-30/31 -- see `crucible_check.py`'s own module docstring for the full incident writeups):
  1. **Wrong pin.** The corpus isn't on the tag `tests/_crucible_pin.py` names. `crucible_check.py` now warns about this automatically (`_check_corpus_pin`) -- if you see the warning, `git fetch --tags && git checkout <tag>` in the corpus checkout.
  2. **Unsafe path.** The corpus's OWN absolute path contains an `IGNORED_DIRECTORIES` name (e.g. `tmp`) as ANY path component, anywhere in the ancestry -- not just the leaf directory name. `guidestar_lens.py`'s documentation-coverage scoring silently skips every such directory, zeroing out that field for the ENTIRE corpus with no error message. `crucible_check.py` now warns about this automatically too (`_check_unsafe_corpus_path`) -- if you see it, move the clone somewhere without `tmp`/`temp`/`cache`/etc. in the path (a true sibling of the repo checkout is always safe).
  If you're pointing `LANGUAGE_CRUCIBLE_PATH` at something other than the standard sibling location, these two checks are the actual thing to verify, not a blanket "always reuse the one pristine directory" rule.
* **Two more environment gotchas, both now handled automatically by `crucible_check.py` --
  worth knowing if you're extending these tools or writing your own scan comparison, since
  neither produces an error message on its own:**
  1. **Python version drift.** CI pins a specific interpreter (`.github/workflows/
     golden-crucible.yml`'s `python-version:`) -- building a venv with a DIFFERENT version
     (e.g. your system default) can resolve different releases of unpinned optional deps
     (`networkx`/`pandas`/etc.), producing numeric drift unrelated to your actual change.
     `crucible_check.py` now prefers a `uv`-managed interpreter matching CI's pin automatically
     (`_find_ci_python`; install `uv` with `curl -LsSf https://astral.sh/uv/install.sh | sh` if
     it's not already on PATH -- one-time, ~10s to fetch the pinned Python version after that).
  2. **`PYTHONPATH` leaking into a venv-specific subprocess.** If the calling shell/script has
     `PYTHONPATH` set to anything containing a real `gitgalaxy/` package (e.g. this repo's own
     root -- an easy thing to have set for an unrelated one-off `python -c` import), a
     subprocess that inherits the full environment resolves `import gitgalaxy` against THAT
     path instead of the venv you actually invoked, silently scanning the wrong code. Every
     subprocess in `crucible_check.py`/`scope_check.py` that must run as a specific venv now
     goes through `_venv_env()`, which strips it. If you add a new subprocess call that invokes
     a venv's python directly, route it through `_venv_env(py)` rather than passing `env=`
     ad hoc or omitting `env=` (which inherits everything, unfiltered).

## 4. Discrepancy Ledgers & Tri-Comparison
* **CI now gates this automatically if you touched `detector.py`/`prism.py`/`language_standards.py`:**
  `tri-comparison-audit.yml` fails your PR if GitGalaxy's own *validated* precision
  (`func_precision`/`class_precision`, read after ledger verdicts are applied — never a raw
  disagreement count) regresses against the committed `tests/tri_comparison_baseline_<lang>.json`.
  Run it yourself before pushing to catch this early: `python tests/tools/tri_comparison_chart.py
  --all --ci` (needs real `ctags` on PATH and the language-crucible corpus — see the README's
  "Reproducing or updating this locally" section). If your fix intentionally improves a language's
  precision, lock it in with `python tests/tools/tri_comparison_chart.py --regenerate --languages
  <lang>` and commit the updated baseline file.
* **You no longer need to manually regenerate the chart/ledger/report before pushing.** A
  push-to-main companion workflow (`tri-comparison-history.yml`) does that automatically once your
  PR merges, opening its own auto-merged PR only if the numbers actually moved. Feel free to still
  run it locally for a sanity check, but it's no longer a required pre-push step the way it used
  to be:
  `python tests/tools/tri_comparison_chart.py --all --write`
  `python tests/tools/tri_comparison_report.py --write`
* **NEVER hand-edit `still_reproduces`:** it's automatically recomputed by the regen script (a
  shape might have multiple contributing causes, so a single fix doesn't guarantee it stops
  reproducing). If you've added a human verdict to an unvalidated shape, only update
  `"status": "validated"`, `"verdict"`, `"investigated_by"`, and `"investigated_at"` by hand.

## 5. Tree-Sitter AST & Accuracy Baseline
* **Audit AST Accuracy:** Run `python tests/tools/tree_sitter_accuracy_audit.py --ci --all`.
  * **Note on Ground Truth Drift:** GitGalaxy supplements tree-sitter ground truth inside blind spots. Improving GitGalaxy's regex precision can therefore cause `real_functions` or `real_classes` (the ground truth) to drop (as false positives are correctly eliminated).
* **Regenerate AST Accuracy Baseline (If needed):** If `tree_sitter_accuracy_audit.py` fails due to ground truth drifting for valid reasons, regenerate the baseline:
  `python tests/tools/tree_sitter_accuracy_audit.py --regenerate --lang <lang>`
* **Regenerate AST Accuracy History & Chart:**
  `python tests/tools/tree_sitter_accuracy_audit.py --history`
  `python tests/tools/tree_sitter_accuracy_audit.py --chart`
  *(Commit the resulting CSV, SVG, baseline JSON, and `language_standards.py` changes.)*

**Note:** Tools that scan the `language-crucible` corpus (such as `crucible_check.py`, `tri_comparison_chart.py`, and `tree_sitter_accuracy_audit.py`) require reading a sibling repository and should be executed using `BypassSandbox=true` or run with proper path resolution.

## 6. Resolving Merge Conflicts on Auto-Generated Files
If `main` advances and causes merge conflicts in `tri_comparison_ledger.json`, `tri_comparison_chart.svg`, or any golden master JSONs, **never attempt to manually resolve the conflict markers**.
1. Check out the upstream version of the files to clear the conflict markers:
   `git checkout origin/main -- docs/self_scan/tri_comparison_chart.svg docs/self_scan/tri_comparison_ledger.json`
   * **CRITICAL LEDGER WARNING**: `tri_comparison_ledger.json` contains *manual annotations* (`status`, `verdict`, `credit_tools`). If you manually validated shapes on your branch, checking out `origin/main` will erase your validations! You MUST back up your manual changes (e.g. write a short Python script to re-apply them), check out `origin/main`, run your script to re-apply your verdicts, and *then* regenerate.
2. Re-run the relevant regen scripts (`crucible_check.py --update --yes`, `tri_comparison_chart.py --all --write`, etc.). The scripts will cleanly recalculate and overwrite the files using your latest code and the upstream's latest ledger baseline.
3. After regenerating, run `python tests/tools/scope_check.py --expect <lang>` once more against `origin/main` (the ref you just merged) to confirm the freshly-regenerated fixture's ONLY real difference from current `main` is your own change -- catches a bad conflict resolution (e.g. accidentally keeping a stale hunk) that a clean regen run alone wouldn't necessarily surface, since regen always "succeeds" even if it baked in something wrong.

## 7. Continuous Integration Monitoring (Agentic)
After pushing your branch and/or opening the PR, you MUST monitor the CI pipeline to ensure it passes.
1. Run `gh run watch` in the background (e.g., using your `run_command` tool with `WaitMsBeforeAsync` set so it detaches to the background) -- Claude Code equivalent: `gh pr checks --watch` via the `Bash` tool with `run_in_background: true`.
2. Do not wait in a polling loop. Once the background task finishes, the system will automatically wake you up with the results.
3. If the CI fails, read the logs, fix the issue, and push the update.
