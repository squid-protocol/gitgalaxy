---
name: rule-contract-audit
description: Take one structural signal from a `draft` row in gitgalaxy/standards/signal_contracts.py to `stated` -- write its one-sentence language-independent contract and corollaries, audit every corpus language's rule against it, fix the rules that disagree (engine PR) with the matching keyword-rosetta plant (corpus PR), and land docs/<rule>_rule_contract.md. Use when the user says "give <signal> a contract", "audit the <signal> rule", "work on #2766/#2772/#2804", or any issue titled "<signal> has no stated contract". Not for adding a language (how_to_add_a_language.md), not for a single-language regex fix (harden-language-extraction), not for a risk formula (that is the commensurability work in docs/contract_roadmap.md Phase 4).
---

A signal's contract is one English sentence saying what one hit is, written so that whoever
adds language 47 counts the same thing the other 46 count. The precedents are
`docs/api_rule_contract.md` (#2730 -> PR #2743), `docs/args_rule_contract.md` (#2773 -> #2786)
and `docs/state_mutation_rule_contract.md` (#2765, the first one run with the tooling below):
a sentence, three or four corollaries, a fallback family for languages with no native form,
then a 46-row audit table. Everything below is that method made repeatable. Read
`docs/contract_roadmap.md` §2 first if the words *stream / count / score* are new.

## Session shape (budget: one session, ~30 tool calls of reading, the rest building)

The #2765 session spent roughly a third of its calls re-deriving things this file now states,
and rebuilt two throwaway scripts that are now `tests/tools/rule_probe.py` and
`tests/tools/bless_scope.py`. Run the legs below in this order, and background every slow one.

```sh
# 0. worktrees -- never edit the primary checkout, never measure against it (it lags main)
cd ~/nyx_projects/gitgalaxy && git fetch -q origin
git worktree add ../gitgalaxy-worktrees/fix-<N> -b fix/<N>-<signal>-contract origin/main
cd ~/nyx_projects/keyword-rosetta && git fetch -q origin
git worktree add ../keyword-rosetta-worktrees/rebless-<N> -b rebless/gitgalaxy-<N>-<signal> origin/main
cd ~/nyx_projects/language-crucible && git worktree add --detach ../language-crucible-worktrees/v1.2.0 v1.2.0   # once; a CLEAN corpus
cd ~/nyx_projects/gitgalaxy-worktrees/fix-<N>
export PYTHONPATH=$PWD GITGALAXY_PATH=$PWD                                  # shadows the .venv's editable install
export LANGUAGE_CRUCIBLE_PATH=~/nyx_projects/language-crucible-worktrees/v1.2.0
export KEYWORD_ROSETTA_PATH=~/nyx_projects/keyword-rosetta-worktrees/rebless-<N>
PY=~/nyx_projects/gitgalaxy/.venv/bin/python
```

## Phase 0 -- read before writing (primary sources, no memory)

1. `gh issue view <N>` and the last comments on the epic (#2812); claim by comment.
2. The signal's row in `gitgalaxy/standards/signal_contracts.py` and its consumers:
   `grep -n '"<signal>"' gitgalaxy/metrics/ gitgalaxy/core/spatial_correlation.py`.
3. **The keyword-rosetta ledger before the rules.** From the corpus worktree at main (the
   primary checkout is usually on a merged feature branch and lags):
   `python3 -c "import json;[print(e['id'],e['disposition'],e['still_reproduces']) for e in json.load(open('deviation_ledger.json'))['entries'] if '<signal>' in json.dumps(e)]"`
   then the verdicts of the ones that matter. Two of the four issues filed from the `args`
   audit were already settled there.
4. Every language's rule, in one view:
   `grep -n -A4 '"<signal>"' gitgalaxy/standards/language_standards/languages/*.py`.
   The corpus plants: `grep -rn -A6 -i "probe_<name>" $KEYWORD_ROSETTA_PATH/data/*/[abc].*`, and the
   manifest cells: every `data/*/expected_signals.json` file's `<signal>` value per file.
5. The baseline incidence, saved (this is half the audit table):
   `$PY tests/tools/rule_probe.py <signal> all --samples 8 --json /tmp/<signal>-before.json > /tmp/<signal>-before.txt`
   -- ~2 min in the background. Read it per language: the most frequent matched lines on the
   real corpus are where a rule is too broad; a corpus cell above the plant is where it is
   too broad or the plant is wrong; a language reading the plant can still be too narrow.
   **If the signal is not a rule** (`unreferenced_by_name`, `duplicate_logic`, anything
   computed in `splice()` from the function list) `rule_probe.py` cannot see it at all --
   use `tests/tools/census_probe.py`, same snapshot/`--compare` shape.
6. **Read the CRUCIBLE rate before the control corpus, for every language the issue accuses.**
   keyword-rosetta says what the corpus planted; the crucible says what the language does. When
   the claim is "this language cannot express X", one crucible number settles it in a single
   call -- #2806 was filed against five languages "whose invocation model never names the
   callee", and real-world ABAP read a 6% unreferenced rate through `PERFORM`, which ended the
   question for four of the five before any code was written. **A corpus cell reading 100%
   defective is not evidence the language cannot answer; check whether the PLANT asks.** Four
   of those five had a `main` whose dispatch unit invoked nothing, where every median language's
   `main` calls its three probes: the cell measured the plant, and the fix was a corpus PR.

## Phase 1 -- the sentence and its corollaries

Write the sentence **without naming any language**. Test it against the shapes every audit so
far has found:

- **Reference vs declaration.** Does a call site / import / type annotation naming the
  construct count? (api: no. haskell `IORef` in a type signature: no. state_mutation: a
  declaration with an initializer is not a write.)
- **Modifier anchored vs bare token.** A bare `\bpublic\b` / `\bvar\b` counts the word; the
  contract must say what the token has to be attached to.
- **Default-relative properties.** Where the language makes the property the default
  (public-by-default, mutable-by-default, no declaration syntax), the contract must say
  whether the declaration itself is the marker (api corollary 3; state_mutation corollary 1's
  fallback) or whether the language records a contract-level absence (immutability_locks,
  #2772). The two answers cannot coexist inside one signal.
- **One statement is one hit, and a token another rule owns is not a second signal.** Check
  the sibling rules (`globals`, `cleanup`, `io`, `high_risk_execution`, `safety_bypasses`)
  for every token you keep; the corpus's `batch4-dual-keyword-overlaps` ledger entry lists the
  known duals and which are deliberate.

Then decide `kind` and `unit` (the module's `KINDS` table) -- Phase 4's commensurability audit
reads them.

## Phase 2 -- edit, then measure; do not measure by hand

Write the rules as a **replacement script** (one python file in the scratchpad with exact
`old -> new` strings asserted to occur once), not as 30 hand edits: it re-applies after a
`git checkout`, and every rule gets the same shared shape (for a statement-level signal, the
`(?:^|[;{}])[ \t]*<lvalue>` anchor with the trailing-comma guard was the whole design).
Then:

```sh
$PY tests/tools/rule_probe.py <signal> all --samples 8 --json /tmp/<signal>-after.json > /tmp/<signal>-after.txt   # background
$PY tests/tools/rule_probe.py <signal> all --compare /tmp/<signal>-before.json /tmp/<signal>-after.json           # the table rows
$PY -m pytest tests/extraction/languages -q -p no:cacheprovider 2>&1 | grep -E "^FAILED|passed"                  # background, ~1 min
PATH=~/nyx_projects/gitgalaxy/.venv/bin:$PATH $PY tests/tools/rosetta_audit.py --corpus $KEYWORD_ROSETTA_PATH --allow-regressions   # background, ~3 min
```

**A registry declaration that is not a regex needs an end-to-end check before anything else
in this phase is believed.** `language_lens.py::_calibrate_lookup_maps` compiles every *string*
value inside a language's `rules` into a regex before a real scan sees it, and neither
`rule_probe.py`, `census_probe.py` nor any unit test goes through the lens -- they build the
extractor from `LANGUAGE_DEFINITIONS` directly. #2806 declared `_invocation_model: "positional"`
inside `rules`, measured exactly the intended result in all three, and recorded the OLD behaviour
in every real scan, because the detector received `re.compile("positional")`. It cost a wasted
golden-master bless. Put a non-pattern helper at the TOP LEVEL of the definition (beside
`lexical_family`), and prove it with one scan of one file:

```sh
$PY -c "import pathlib;pathlib.Path('/tmp/one/x.<ext>').write_text(...)"   # or copy a corpus file
git -C /tmp/one init -q && git -C /tmp/one add -A && git -C /tmp/one commit -qm x   # the census needs git-tracked files
.crucible_venvs/zero_dependency/bin/galaxyscope /tmp/one --output /tmp/one_out --db-only
sqlite3 /tmp/one_out/*_master.db "select file_path, <column> from file_data;"
```

The three run in parallel. Read the after-samples for every language whose count moved more
than expected in *either* direction (abap went 48 -> 792 on a first draft because multi-line
named parameters look like assignments; the statement-period guard took it to 402). Expect a
few languages to widen (dart, abap, javascript: the construct had been invisible) and most to
narrow. `rosetta_audit` prints `expected N, got M` per file: every line is either a rule fix
(cell was wrong) or a plant authored to the old rule (re-plant), and the doc says which.

Screen every re-plant as a **replacement pair** against the branch rules (keyword-rosetta's
`tools/screen_plant.py` hard-codes the primary checkout; use an inline
`LANGUAGE_DEFINITIONS[lang]["rules"]` loop under PYTHONPATH instead) so the new plant fires
nothing else that is gated -- `AtomicInteger` was carrying an unplanted `concurrency` hit, and a
`const` decoy would have moved `immutability_locks`.

## Phase 3 -- engine PR (one layer only)

- Rule edits with a `# #<N> contract:` comment naming the corollary each exclusion serves.
- Strict tests: flip the per-language pairs the contract reverses (expect ~10) and rewrite the
  "intentional double-classification" tests the contract retires (dockerfile ENV, m4 popdef,
  matlab clear were all pinned as *deliberate* duals). Put the contract itself in ONE
  cross-language module, `tests/extraction/languages/test_<signal>_contract_<N>.py`: a
  `CASES = {lang: (positives, negatives)}` table, a `COUNTS` table for one-statement-one-hit,
  and one ReDoS detonation over the shared payload list for every language.
- `ruff format` ONLY the files you touched -- `ruff format .` reformats ~20 test files that
  main has never formatted, and you will have to `git checkout` them back. A mechanical rename
  touches files you never opened: format the whole CHANGED SET (`git diff --name-only`), not
  just the ones you hand-edited, and do it BEFORE `audit_check.py --regenerate` -- formatting
  moves line numbers, so a baseline regenerated first comes back as a new finding in CI (two
  wasted pushes on #2806).
- Sheet: flip the row to `status="stated"`, set `doc=`; update the schema comment line in
  `how_to_add_a_language.md` so it *contains* the contract sentence; then
  `$PY tests/signal_contract_audit.py --regenerate-baseline --render` and `--ci`.
- `docs/<signal>_rule_contract.md` in the api/args/state_mutation shape; the audit table comes
  from `rule_probe.py --compare`.
- Bless from the clean corpus worktree and scope it before committing:
  `git show HEAD:tests/golden_master_zero_dep_audit.json > /tmp/old.json`
  `LANGUAGE_CRUCIBLE_PATH=... $PY tests/tools/crucible_check.py --update --yes` (background,
  first run in a worktree builds two venvs, ~4 min; later runs ~2 min)
  `$PY tests/tools/bless_scope.py /tmp/old.json tests/golden_master_zero_dep_audit.json`
  -- the leaf-key table must name only the signal and the formulas that read it; a file in
  "newly parsed / newly excluded" means a rule change crossed the aperture's density guard.
- Gauntlet legs, all in the background: full `pytest tests/`, `ruff_audit --ci`,
  `mypy_audit --ci`, `dead_key_audit --ci`, `tests/tools/audit_check.py`.
- Before opening either PR, re-run `rosetta_audit.py` once more against the corpus branch and
  drive it to 46/46. A signal change moves the cells DERIVED from it, not only its own:
  #2806's last regression was jcl's `api_orphan_credit`, three files, found only there.
- Label `rosetta:rebless-owed`. One `Closes #N` per line. File the follow-ups the audit
  deferred *before* writing the doc, so the doc links them.

## Phase 4 -- corpus PR (keyword-rosetta), branch pushed before the engine PR merges

Manifests round-trip with `json.dumps(d, indent=2, ensure_ascii=False) + "\n"`; the ledger with
`ensure_ascii=True`. Per language whose cell or plant moved: the cell, a dated sentence in
`notes`, and the plant. One new ledger entry for the contract (`upstream-bug`,
`still_reproduces: false`, the verifying scan named), plus edits to the entries the contract
retires (`batch4-dual-keyword-overlaps` lost matlab and m4 to #2765). Verify every language
against the branch engine (`GALAXYSCOPE_BIN=<main .venv>/bin/galaxyscope` with the PYTHONPATH
above; loop `tools/verify_language.py <lang>` over `data/*`), regenerate the bias report at full
precision, push, open the PR with the Cross-repo note. It goes green when engine main carries
the engine PR.

## Done criterion

The module row is `stated`; `signal_contract_audit.py --ci` exits 0 with a smaller baseline;
`rosetta_audit.py` against the re-blessed corpus is 46/46; the bias report's open-defect share
for the metrics this signal feeds did not rise; every red cell that remains on this signal is
`inherency` or `echo` in the report's cause table, or has a filed issue the doc links.
