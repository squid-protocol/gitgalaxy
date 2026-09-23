---
name: add-signal
description: Introduce or activate a signal key across the whole language registry -- the scope decision (dormant slot vs new key vs sec_ observer), the contract trio, a rule or stated-absence None in every sibling-set language, the one-owner adjudication (including re-homing a construct between signals), strict-test baseline pins, and the leaf-only golden-master bless. Use when the user asks to "add a signal", "activate <key>", "give <construct family> an owner", or a census/issue reports a construct with no base-schema owner (#3004's shape). NOT for adding one language (add-language), deepening one language's existing rules (harden-language-extraction), or per-signal contract audits of an existing live signal (rule-contract-audit).
---

Built from the #3004 `auth_middleware` activation (PR #3157: 26 rules + 12 stated absences
across the 38-language sensor set, one construct re-homed, one CI round-trip that this skill
exists to save you). Read these and nothing else before writing code:

1. `gitgalaxy/standards/signal_contracts.py` — the docstring, the `SignalContract` dataclass,
   and the hybrid-sensor `_c(...)` rows (your row's template);
2. `gitgalaxy/standards/how_to_add_a_language.md` OUTPUT SCHEMA — the `# key:` comment style
   (sentence + Includes + EXCLUDES) and where your key slots in;
3. `docs/domain_sensor_contracts.md` — the #2897 batch record and the #3004 addendum (the
   precedent for adding a sensor to the family after the batch);
4. the sensor block of two shipped languages: `languages/python.py` (call-anchored idiom
   lists) and `languages/hlasm.py` (`_STMT`/`_OPEND` statement anchoring) — every rule you
   write must read like its file's neighbors, not like each other.

## Step 0 — the scope decision (everything downstream hangs on it)

Classify the change FIRST; each class has different model consequences
(`signal_processor.py:38-69` and the frozen-placeholder comments in `analysis_lens.py`
are the ground truth):

- **Activating a dormant slot** (auth_middleware's case: key already in `SIGNAL_SCHEMA`,
  `SHORT_KEY_MAP`, `DNA_SOURCES`, `SURFACE_FAMILIES`, zero producers): vector width is
  unchanged, `feature_contract_sha` and `test_archetype_parity`'s pins DO NOT move — if the
  sha moves, stop, something else is wrong. But the dimension goes constant-zero → live, so
  an archetype retrain (`train-archetypes` skill) is owed AT merge, not eventually.
- **Brand-new non-`sec_` key**: widens the archetype vector — retrain AND
  `EXPECTED_CONTRACT_SHA` re-pin are mandatory, plus all four wiring sites in
  `analysis_lens.py` and a `record_keeper.py` short key. Budget accordingly.
- **`sec_`-prefixed observer**: dimension-free (excluded from the archetype vector); only
  the contract/audit/recorder surfaces apply.
- **Re-homing a construct between existing signals** (GRANT/REVOKE encapsulation →
  auth_middleware): no schema change at all, but BOTH rule comments move, and the strict
  tests must pin the migration in BOTH directions (positive on the new owner, negative on
  the old) or the move silently regresses.

## Environment

    eval "$(tests/tools/worktree_env.sh signal-<issue> --corpus 2>/dev/null)"

Batch crucible scans need the Bash sandbox off (mega-repos get reaped) and
`GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER` (a 5s license delay otherwise skews anything
timed). `pytest -x` is a trap in this repo: the pre-existing fidelity-freshness failure in
`tests/core_engine/` aborts the run before `tests/extraction/` ever executes — the #3157
strict-test failures reached CI precisely because of a local `-x` run. Run the full suite
without `-x` and triage the tally instead.

## The order (each gate is cheaper than the next)

1. **Contract trio, then render.** `_c(...)` row in `signal_contracts.py` (phase/kind/status
   copied from the nearest sibling, your issue number), the `# key:` OUTPUT SCHEMA comment,
   the evidence-doc section. Then `python tests/signal_contract_audit.py --render` — the
   rendered `docs/signal_contracts.md` is generated, never hand-edited. Audit sequencing to
   know: `orphan-contract` fires while no language defines the key (fine mid-PR);
   `missing-contract` fires the moment one does — land the trio and the rules together.
2. **Rollout parity = the sibling set, exactly.** The canonical "real language" set is the
   files carrying `serialization_parsing` (38 today); data/markup formats carry no sensor
   keys at all. Every file in the set gets a rule OR an explicit `None` with a one-line
   morphology rationale — an absent key is an unreviewed absence. Verify with one line:
   `set(has(new_key)) == set(has("serialization_parsing"))` over `LANGUAGE_DEFINITIONS`.
3. **One construct, one owner — grep BEFORE writing.** For every candidate token, grep the
   target file's existing rules first. #3004's catches: shell `sudo` was already
   high_risk_execution's, solidity `onlyOwner`/`require(` were safety's, dockerfile `USER`
   was split between safety (`USER nonroot`) and safety_bypasses (`USER root`) — each became
   a rationale line in the rule comment or the `None`, not a double-count.
4. **Anchoring discipline (#2899).** The stream strips comments but NEVER masks strings, so
   a bare word false-positives on string content; and bare words match identifiers — the
   #2990 census's "SIGNON n=14" was entirely paragraph names (`SEND-SIGNON-SCREEN`), zero
   real commands. Anchor every idiom to its invoking form (call `(`, annotation, statement
   position, `EXEC`-prefix) and guard self-definitions with fixed-width lookbehinds
   (`(?<!def )`, `(?<!fun )`). Honor per-file conventions: hlasm's `_STMT`/`_OPEND`, cobol's
   `(?i)` + `EXEC\s+CICS` anchors, db2's `^[ \t]*` statement anchors.
5. **Validation ladder.** (a) import `LANGUAGE_DEFINITIONS` — compiles everything; (b) a
   scripted positive/negative sweep (keep the fleet's tricky negatives); (c)
   `python tests/tools/rule_probe.py <key> <lang> --samples 3` per rule language against the
   crucible — eyeball every densest-match line; an honest mostly-zero result is fine
   (ssr_boundaries precedent), a noisy one is a rule bug; (d) if mainframe verbs are
   touched, `tests/tools/embedded_verb_coverage.py cobol --check` and `jcl --check` — update
   the EXPECTED verdict rows (a 0-occurrence ownership row is legal: the NATIVE:WHENEVER
   "engine-correctness ahead of corpus evidence" posture).
6. **The six pinned strict suites — do these BEFORE pushing, not after CI.** db2_sql, hlasm,
   pli, rexx, ada, bms pin `_BASELINE_KEYS`, `_EXPECTED_NONE_KEYS`, and one
   positive/negative case per live rule (`test_every_non_none_rule_has_a_simple_case`).
   Add the key to all six baselines, to the None-sets where the rule is `None`, cases where
   it is live, and move any re-homed construct's cases/separations/pathological rows to the
   new owner. Then run `pytest tests/extraction/languages/ -q` in full.
7. **Full audits.** `signal_contract_audit.py --ci`, `dead_key_audit.py`,
   `pytest tests/core_engine/` (parity + vector width), then the whole suite without `-x`.
   Known environmental reds in a zero-dep venv: the ML-gated `test_security_auditor` block
   and the fidelity-freshness pin — confirm they fail identically on an unmodified main
   worktree before blaming your diff, and say so in the PR.
8. **Golden masters — leaf-only, both fixtures (#3005 discipline).** Scan the crucible with
   the branch engine (`PYTHONPATH` beats the editable install, so the venv's `galaxyscope`
   runs your worktree): `GITGALAXY_DISABLE_GIT_HISTORY=1` + the license key, then diff with
   `tests/golden_diff.py`. Every structural mismatch must be your signal's leaves; patch
   exactly those into BOTH `golden_master_audit/` and `golden_master_zero_dep_audit/`
   — never `--update` wholesale. Traversal: group keys are directory paths
   (`"solidity/openzeppelin"`), files live under `[group]["Files"][path]`, the per-file node
   is `"7. Structural Signatures (Net Mitigated Signals)"` keyed by the FRIENDLY name
   (`"Auth Middleware"`, not `def_auth`), zeros already present. Serialize with
   `json.dumps(d, indent=4, ensure_ascii=True)` — any other convention rewrites the 58MB
   file (a 0.16.6-formatted dump shrank it 14MB; content-equal, diff-poisoned). Sanity: the
   byte delta should be roughly the digits you changed. Dep-context mismatches
   (`Missing Dependencies/...`, `Zero-Dependency Mode Active`) are your local env, not drift.
9. **CI formatting.** The zero-tolerance `ruff format --check` runs pinned `ruff==0.16.0`
   over `gitgalaxy/` ONLY (`tests/ruff_audit.py`'s `SCAN_ROOT`). The v6 venv's newer ruff
   formats implicit string concats differently — check with the pinned version
   (`pip install --target <scratch> ruff==0.16.0`) and ignore its complaints about `tests/`.

## Delegation

Fleet-drafting the per-language vocabulary (agy or any cheap model) is the right call — 33
languages of "what is this language's auth/serialization/X surface" is research, not
adjudication. But every draft regex gets the same three-step review before it lands: tighten
to the sibling discipline (3–10 idioms, anchored), grep its tokens against the file's
existing owners (step 3), and probe it against the crucible (step 5c). #3004's fleet drafts
needed all three: dropped generic tokens (`signIn`, bare `authorize`), caught two mislabeled
"negatives" that were real positives, and two miss-shaped patterns (turbofish
`decode::<T>(`, a dropped library family). Never delegate: the scope decision, ownership
adjudication, re-homing, golden-master forensics, the PR narrative.

## After merge

- Retrain if a dimension went live (scope classes 1–2); parity shas move only in class 2.
- keyword-rosetta needs nothing by default: menus and tier reports regenerate from the live
  registry, and unplanted-signal `None`s are NOT ledger-gated (no sibling sensor None has a
  deviation-ledger entry — the n/a gate covers planted signals only). The fidelity table
  moves only if rosetta plants the signal.
- The census/coverage docs keep their measured tables; resolutions are appended (the
  `cobol_semantic_coverage.md` finding-4 pattern), never rewritten.
