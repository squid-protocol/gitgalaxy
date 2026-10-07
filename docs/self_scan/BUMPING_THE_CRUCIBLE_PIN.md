---
description: "This is the complete, ordered procedure for moving GitGalaxy's pinned"
---
# Bumping the language-crucible pin: the full checklist

This is the complete, ordered procedure for moving GitGalaxy's pinned
`language-crucible` corpus from one tag to another. It exists because the
first real bump after the pin was consolidated (`v1.0` → `v1.1.0`) still hit
four rounds of CI failures — golden masters, then a corpus_path baking-in
bug, then a tree-sitter-accuracy baseline gate, then the tri-comparison/
tree-sitter-accuracy charts nobody had touched at all. Every one of those was
independently discoverable in advance; this doc collects them into one place
so the next bump finds them in one pass instead of four.

**Read `docs/self_scan/README.md` and `docs/self_scan/tri_comparison_README.md`
first** for what each system actually measures — this doc is the *procedure*,
those are the *why*.

## Prerequisites (check these before touching anything)

- [ ] **Real Universal Ctags on PATH**, not a shadow. `ctags --version` must
  print `Universal Ctags`, not error out or print an Arduino banner (Ubuntu's
  `arduino-ctags` package installs as `arduino-ctags`, not `ctags`, so a
  missing-not-shadowed `ctags` is the more common failure mode — but confirm,
  don't assume). Install via `apt install universal-ctags` if missing. A
  missing/wrong ctags doesn't error loudly — languages just silently degrade
  to a 2-tool comparison (see PR #2111, which reverted several validated
  badges this way without a single error message).
- [ ] `pip install tree-sitter-language-pack` in whatever environment runs
  the regeneration scripts below.
- [ ] **The new corpus is checked out as a sibling directory literally named
  `language-crucible`** (or `LANGUAGE_CRUCIBLE_PATH` points at it) — not
  some other local name. `corpus_path` gets baked verbatim into every
  regenerated baseline file from whatever that directory is named; a
  differently-named local checkout produces a baseline that spuriously fails
  the very next real CI run, which clones as `language-crucible`. (Real
  incident this pass — corrected by hand before committing; see the
  `tree_sitter_accuracy_baseline_*.json` fix in the v1.1.0 bump PR for what
  that correction looked like.)
- [ ] **That checkout is `git status`-clean** — no untracked or ignored
  files. `galaxyscope` scans the filesystem broadly; a stray cache directory
  or `__pycache__` sitting in the corpus gets scanned and can silently bake
  into a fixture. (Real incident this pass — a `data/.gitgalaxy/` dependency-
  cache directory, confirmed harmless only by cleaning it and re-running to
  see "no drift" either way. Don't assume harmless without that check.)
  Re-check after *every* regeneration step below, not just once up front —
  several of these tools recreate their own cache artifacts as a side effect
  of running.

## The steps, in order

1. **Golden master fixtures** — `tests/tools/update_golden_master.py --yes`,
   once per dependency mode (full-precision / zero-dependency; it only
   updates whichever matches your current environment's installed
   packages). Do this *before* touching the pin — `flag-golden-master-changes`
   is non-blocking, but the pin's whole job is to make this fixture
   reproducible, so get it right first.
2. **Tri-comparison chart + ledger** —
   `tests/tools/tri_comparison_chart.py --all --write` (always `--all`, per
   `.claude/rules/tri-comparison-chart.md` — a partial `--languages` list
   with `--write` overwrites the whole file with only those languages).
   Expect new `unvalidated` ledger entries for any language whose corpus
   content changed; expect zero removed entries and zero reverted `status`
   fields. Anything else in the diff is a red flag, not routine.
3. **Tri-comparison points-of-interest doc** —
   `tests/tools/tri_comparison_report.py --write`. Cheap, reads the
   just-refreshed ledger, no live scan.
4. **Tree-sitter-accuracy history + chart** —
   `tests/tools/tree_sitter_accuracy_audit.py --history` then `--chart`.
   Purely observational (never touches the gating baseline JSON files), safe
   to run regardless of step 5's outcome.
5. **Check for stale tree-sitter-accuracy baselines** —
   `tests/tools/tree_sitter_accuracy_audit.py --all --ci`. Any language
   reporting "ground-truth metric(s) drifted" has a stale baseline because
   its corpus content actually changed. For each one:
   - **Read the printed examples first** (`_missing_examples`,
     `_extra_examples`, `_extra_class_examples`, `_args_mismatch_examples`).
     A drift is not automatically "just corpus growth" — it can also surface
     a real, previously-untested regex false-positive. Distinguish before
     regenerating; don't rubber-stamp.
   - `--regenerate` writes the new baseline cleanly *if* no `_regressions()`
     gate trips (compares raw `extra_functions`/`extra_classes` counts
     against the old baseline). **This gate does not account for corpus
     size changes** — a 20-200x file-count increase mechanically produces
     more absolute false-positive hits even at a flat or improved per-file
     rate, and will refuse every time on a category that grew substantially.
     See "Known gap" below for the state of a real fix; today, this needs a
     maintainer to explicitly accept the drift after reading the examples,
     currently by directly calling `measure()` + writing the baseline file
     without going through `run_regenerate()`'s gate (see the v1.1.0 bump
     PR's baseline-fix commit for exactly what that looked like and how the
     reasoning was documented in the commit message).
6. **Bump the pin**, in the same PR: `python tests/tools/crucible_pins.py bump language vX.Y.Z`
   (it edits `tests/crucible_pins.toml`, the only source; the `LANGUAGE_CRUCIBLE_REF` repository variable is no
   longer read by any workflow, `crucible_pins.py check` warns if it lags). After the merge, move the shared
   checkouts with `python tests/tools/crucible_pins.py sync`.
7. **Grep for the old tag string** across the whole repo as a final check —
   `grep -rn "vOLD\.TAG" --include="*.py" --include="*.md" --include="*.yml" .`
   A workflow added since the last bump could have hardcoded a fresh literal
   instead of `crucible_pins.py get language`.
8. **Push, then watch CI actually pass** before merging —
   `crucible-audit` (both modes), `tri-comparison-audit`,
   `tree-sitter-accuracy-audit`, `flag-golden-master-changes`, and
   `crucible-path-independence` (#4248: scans the new corpus from a neutral parent
   and from `tmp/docs/vendor/src/`, fails naming the leaves if they differ; run it
   by hand with `python tests/tools/crucible_path_check.py` since it only
   triggers on engine changes). A local
   `--ci` run is a fast pre-check but isn't a substitute: a differently-named
   local checkout makes the `corpus_path` field look like it drifted even
   when nothing about the corpus changed.

## Traps found on the v1.3.0 bump (#3117 / #3138)

Three things cost real time on that bump that this checklist did not warn about.
All three are now either fixed or guarded, but the symptoms are worth
recognising because two of them present as "CI is broken" rather than as
anything to do with the corpus.

1. **Two `Code scanning results` checks time out after 6 minutes, and the PR
   shows "0 files changed, +0/-0".** This is not a failure of the change and
   re-running the checks cannot fix it. A fixture that size produces a diff
   GitHub will not generate (`/pulls/<n>/files` answers HTTP 422, "Sorry, this
   diff is taking too long to generate"), and the code-scanning checks that
   reconcile alerts against a diff then hang until their budget runs out.
   `.gitattributes` now marks both fixtures `-diff linguist-generated=true`,
   which should prevent it; if it recurs, confirm the other checks are green
   and review the change semantically (see point 3) rather than chasing the
   scanners. Note that the repo's *own* `CodeQL Security Scan` and `Muninn
   Security Scan` workflow runs are separate from the `Code scanning results /`
   check-runs and did pass — check which of the two you are looking at.
2. **A `list(set(...))` anywhere on the recorder path makes the fixture
   nondeterministic**, so a bless captures set-iteration order and the very
   next check disagrees with it for no reason anybody changed. `api_mapper`'s
   `frameworks` and `shadow_apis` did exactly this and are now `sorted(...)`
   in `full_api_network_map.py`. If a bless shows drift you cannot attribute,
   scan the recorders for unsorted set-to-list conversions before assuming the
   engine changed. Beware also that verifying this from a subshell that `cd`s
   elsewhere makes `PYTHONPATH=.` resolve to the wrong tree — the first
   attempt at confirming that fix was invalid for exactly that reason.
3. **Review the bless semantically; the line diff is not a review.** On #3138
   git reported 231,550 insertions and 186,273 deletions, of which 0.5% of leaf
   values had actually changed. `tests/tools/bless_scope.py` reduced the same
   change to 349 substantive differences and 3,246 topological X/Y/Z re-solves
   (the expected corpus-wide 3D coordinate shift from adding groups), bucketed
   by section, leaf key and language:

       python tests/tools/bless_scope.py --from-head tests/golden_master_audit --show 0 --summary

   Read the topological volume as a class and spend the review on the
   substantive bucket.

## Known gap worth fixing properly

Step 5's absolute-count regression gate is the one manual, judgment-requiring
step in an otherwise mostly-mechanical checklist, and it's manual for a bad
reason (a metric that doesn't normalize for corpus size), not a good one
(genuine need for human judgment on every bump). A `--force`/`--accept`-style
flag on `tree_sitter_accuracy_audit.py --regenerate` — one that still prints
the regressions being overridden (so they're visible in the PR diff for
review, same as everything else in this codebase's "never silently
overwrite" philosophy) rather than requiring a maintainer to hand-write a
one-off bypass script each time — would close this properly. Not implemented
here; flagged for a follow-up issue.

## The CICS crucible pin (`[cics]` in `tests/crucible_pins.toml`): re-prove the committed ports (#4308)

The CICS crucible (squid-protocol/cics-crucible) has its own pin and its own bump, described in
`tests/crucible_pins.toml` and `docs/ecosystem.md` ("CICS crucible release -> pin bump"). It is one PR:

1. Check the crucible out at the new tag (`CICS_CRUCIBLE_PATH`, or `../cics-crucible`), and move the pin with `python tests/tools/crucible_pins.py bump cics <tag>`.
2. `python tests/tools/cics_crucible.py --update-baseline`, then commit `tests/cics_crucible/baseline.json`,
   `tests/cics_crucible/coverage.json` and `docs/language_status/cics_crucible.md`. Explain every cell that moved.
3. **Re-prove the committed ports and re-stamp their provenance.** Every
   `tests/cics_crucible/ports/<case>/<PROGRAM>/provenance.json` names the crucible version its proof ran at, and
   `tests/cics_crucible/test_port_provenance.py` fails until each one is at the new pin. Run
   `python tests/tools/crucible_port_provenance.py reprove` (Docker, a JDK 17 and Maven). It runs
   `cics_crucible.py --cases C --program P --sides java-ported --report-dir ...` for each port at the pinned checkout
   and writes the outcome into the record:
   - proven: a `proof.reproven` entry is **appended** (the crucible ref, the per-scenario summary, the port tree's
     sha256, the harness commit). The loop's own `proof.crucible_ref` and `history` are never rewritten: they say
     how and where the port was first proven.
   - not proven: `proof.stale` = `{against: <new pin>, reason, needs}`. The test accepts it, because the record now
     says it is stale. Say in the PR which ports went stale and why; fixing a port is a `port_runner prove` loop of
     its own, not part of the bump.
   Never write a `reproven` entry by hand: only `reprove`, which runs the proof, writes one.
   `python tests/tools/crucible_port_provenance.py check` lists the records that are still behind.

The evidence record (#4048) recomputes staleness from fingerprints instead of storing it. The `crucible` input it
records is this pin, so a bump makes every crucible port's evidence stale until it is re-proven here.
