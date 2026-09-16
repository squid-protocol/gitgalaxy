---
name: add-language
description: Add a brand-new language to GitGalaxy end to end -- the languages/<lang>.py profile, every registration surface (lens collision table, detector dispatch/allowlists, strictness/ecosystem rows, the positional-family pin), the strict test suite, golden-crucible verification, docs, the keyword-rosetta control folder, and the paired engine+corpus PRs. Use when the user asks to "add language X", "implement issue #NNNN" for a Language Addition issue, or names a language the registry doesn't have. NOT for deepening an existing language's rules (harden-language-extraction / harden-strict-signatures) or documenting one (language-status).
---

Source of truth is `gitgalaxy/standards/how_to_add_a_language.md` — the generation prompts,
the 19 CRITICAL ENGINE RULES, the output schema, the **Decision tables** (settle
signal-ownership and the positional-census question by lookup there, never by re-reasoning),
and the Strict Testing framework all live in it. This skill is the ordered path through it
plus everything the doc's steps assume you already know. Read these and nothing else before
writing code — do NOT spend an exploration pass re-deriving the checklist:

1. `gitgalaxy/standards/how_to_add_a_language.md` (all of it, once);
2. the two nearest template profiles — `languages/sqlite.py` + `languages/pli.py` cover the
   SQL-dialect and mainframe families; pick whichever is closer to the target, plus the most
   recently added language (`git log --oneline -- gitgalaxy/standards/language_standards/languages/`);
3. one strict suite as the test template (`tests/extraction/languages/test_db2_sql_strict.py`
   is the newest full-shape example: routing tests, one-statement-one-hit counting, the
   ReDoS detonation sweep);
4. keyword-rosetta's `SPEC.md` (the corpus half's authoring contract; the verifier is the
   reviewer there).

## Environment (never hand-assemble this)

    eval "$(tests/tools/worktree_env.sh <lang>-<issue> --corpus 2>/dev/null)"

gives the engine worktree, the corpus worktree, and the five exports (PYTHONPATH-first is
load-bearing). Branch the engine worktree as `lang/<lang>-<issue>` and the corpus one as
`corpus/<lang><issue>`. Golden-crucible runs use the dedicated envs at
`.crucible_venvs/{full_precision,zero_dependency}` (run once per env; the test picks its
fixture from the env it runs in).

## The order (each gate is cheaper than the next; don't skip ahead)

1. **Profile + registration** (Steps 1–3): `languages/<lang>.py`, `__init__.py`, plus the
   wiring the audit below enumerates (collision table, detector alias/allowlist, strictness
   row, ecosystem set, positional pin if applicable).
2. **`python tests/tools/language_addition_audit.py --lang <lang>`** (~5s): hard failures
   are future red CI runs; fix them all before running anything slower.
3. **Smoke the rules by hand** (~1 min): a realistic snippet through each headline rule with
   `finditer`, and `StructuralExtractor(...).splice(...)` for the extraction shape. Cheaper
   than a test suite and catches regex arithmetic immediately.
4. **Rosetta shell + `--report`** (~30s, the best semantic oracle in the pipeline): author
   `data/<lang>/` per SPEC.md in the corpus worktree, commit (the census only walks tracked
   files), then `python tools/verify_language.py <lang> --report --engine <engine-worktree>`.
   Explain every observed count before locking the manifest; an unexplainable delta is a
   stop-and-investigate, possibly a real engine bug — on db2_sql this step caught a census
   contract violation the entire engine suite couldn't see.
5. **Strict suite** (Step 4's separate adversarial pass) + `pytest tests/extraction -q`.
6. **Golden crucible**, both envs; explain every diff by name (`golden_diff.deep_compare`,
   never the truncated pytest message) before `update_golden_master.py --yes`, once per env.
   Regenerate fixtures only once, immediately after a fresh rebase onto origin/main —
   fixtures conflict as a unit, so mid-flight main movement means regenerate-again.
7. **Docs** (`language-status` skill → `docs/language_status/<lang>.md` + index row), then
   the full default suite ONCE, then ruff/ruff-format/mypy on touched files.
8. **Both PRs together**, cross-referencing: engine PR explains the golden-master diff
   (on-target/off-target split, zero language flips or say why not); corpus PR carries the
   bias-report result (`tools/bias_report.py --engine <worktree>`, full-precision crucible
   venv) with every new out-of-band cell ledgered — join an existing deviation-ledger entry
   where the shape already has one before minting a new id. Bias-report artifacts
   (docs/bias_*.md/json/svg) are NOT committed; the auto-updater regenerates them post-merge.
   After both merge: check whether `fidelity_table.py`'s FIDELITY_PROVENANCE re-pin is owed
   (the audit's --lang warning says so).

## Model delegation (keep the expensive model for judgment)

The three generation passes are machine-gated, so draft them with a cheaper/different-family
model — `gemini -p "$(cat prompt.txt)"` works from this environment — and let the gates judge:

- Step 2's rules dict (feed the doc's Generation Prompt + the chosen template profile; gated
  by the audit tool, the smoke pass, and the strict harness's ReDoS detonation);
- Step 4's strict-suite skeleton (the doc *requires* a separate adversarial pass — a
  different model family than the rules' author is better separation than a fresh session);
- the rosetta shell draft (SPEC.md hands itself to a model verbatim; `verify_language.py`
  is the reviewer, "correct by construction").

Never delegate: signal-ownership adjudication (Decision tables first, contracts second),
engine wiring, golden-master/bias-report diff forensics, deviation-ledger entries, and the
PR narratives. Those are the places #2511's only real mistakes happened or were caught.
