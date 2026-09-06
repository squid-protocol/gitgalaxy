---
name: rule-contract-audit
description: Take one structural signal from a `draft` row in gitgalaxy/standards/signal_contracts.py to `stated` -- write its one-sentence language-independent contract and corollaries, audit every corpus language's rule against it, fix the rules that disagree (engine PR) with the matching keyword-rosetta plant (corpus PR), and land docs/<rule>_rule_contract.md. Use when the user says "give <signal> a contract", "audit the <signal> rule", "work on #2765/#2766/#2772", or any issue titled "<signal> has no stated contract". Not for adding a language (how_to_add_a_language.md), not for a single-language regex fix (harden-language-extraction), not for a risk formula (that is the commensurability work in docs/contract_roadmap.md Phase 4).
---

A signal's contract is one English sentence saying what one hit is, written so that whoever
adds language 47 counts the same thing the other 46 count. The precedent is
`docs/api_rule_contract.md` (#2730 → PR #2743) and `docs/args_rule_contract.md` (#2773 → #2786):
a sentence, three or four corollaries, a fallback family for languages with no native form,
then a 46-row audit table. Everything below is that method made repeatable. Read
`docs/contract_roadmap.md` §2 first if the words *stream / count / score* are new.

## Phase 0 — read before writing (primary sources, no memory)

1. The signal's row in `gitgalaxy/standards/signal_contracts.py`: kind, unit, the draft
   sentence, and which risk formulas read it (`grep -n '"<signal>"' gitgalaxy/metrics/`).
   A signal with no scored consumer is a lower priority than one under `risk_*`.
2. **The keyword-rosetta ledger before the rules.** `deviation_ledger.json` entries whose
   `signal` names this key, and the manifest `notes` for the languages they cite. Two of the
   four issues filed from the `args` audit were already settled there (#2773 follow-up) --
   a rule is not a defect until you have read the verdict that may already explain it.
3. Every language's rule, in one view:
   `grep -n -A2 '"<signal>"' gitgalaxy/standards/language_standards/languages/*.py`.
   Note which are `None` and why (the inline comment).
4. The open issues: `gh issue list --search "<signal> in:title" --state all`.

## Phase 1 — the sentence and its corollaries

Write the sentence **without naming any language**. Test it against the three shapes every
audit so far has found:

- **Reference vs declaration.** Does a call site / import / type annotation naming the
  construct count? (api: no. haskell `IORef` in a type signature: no, per #2765.)
- **Modifier anchored vs bare token.** A bare `\bpublic\b` / `\bstatic\b` counts the word;
  the contract must say what the modifier has to be attached to.
- **Default-relative properties.** Where the language makes the property the default
  (public-by-default, immutable-by-default), the contract must say whether the declaration
  itself is the marker (api corollary 3) or whether the language records a contract-level
  absence (immutability_locks, #2772: `let` in swift is an annotation chosen against `var`;
  `let` in rust is not an annotation, so rust counts only `const|static` and ledgers the rest).

Then decide `kind` and `unit` (the module's `KINDS` table) -- this is what Phase 4's
commensurability audit reads, so get it right here: is one hit a *declaration*, a code
*site*, an *annotation* attached to something, or a vocabulary *token*?

## Phase 2 — audit all 46 against the sentence

Two instruments, both cheap, both in keyword-rosetta:

```sh
# 1. does this text fire this rule (and what else does it fire)? -- a replacement PAIR,
#    never a lone plant: screen the old form and the new form side by side (#71 lesson)
cd ../keyword-rosetta && python tools/screen_plant.py <<'EOF'
[("swift", "let total = 0", "immutability_locks"), ("swift", "static let total = 0", "immutability_locks")]
EOF

# 2. real-world incidence per alternative, on the language-crucible corpus -- measured on the
#    Prism CODE STREAM the rule actually sees, not raw files (memory: #2674):
#    scan a detached worktree of origin/main, never the working tree (a stale plant produced a
#    phantom outlier on 2026-09-05), and set GALAXYSCOPE_BIN to that worktree's install.
```

The output is the audit table: `| language | rule matches | contract says | verdict |` with one
of *agrees / too broad (counts X) / too narrow (misses Y) / no native form → fallback / None*.
Expect the #2743 shape -- a few languages widen, most narrow -- and expect the ledger to already
explain some rows.

## Phase 3 — engine PR (one layer only)

- Rule edits + strict positive/negative tests in `tests/extraction/languages/test_<lang>_strict.py`,
  ReDoS detonation for any new quantified regex (CRITICAL ENGINE RULES 5, 9, 13, 14).
- Update the signal's comment line in `how_to_add_a_language.md` to the contract sentence
  (the audit checks containment), flip the module row to `status="stated"`, set `doc=` and
  `issue=`, then `python tests/signal_contract_audit.py --regenerate-baseline --render`.
- `docs/<signal>_rule_contract.md` in the api/args shape.
- Attribute the golden-master diff per language before blessing (CLAUDE.md "Scoping a bless");
  revert-one-rule to attribute a surprising mover (memory: CICS hardening).
- Label `rosetta:rebless-owed` if the corpus moves. One `Closes #N` per line.

## Phase 4 — corpus PR (keyword-rosetta), after the engine PR merges

Plant or re-plant per the contract (SPEC.md), ledger contract-level absences with
`disposition: intended-morphology` naming the signal and the languages, retire entries the fix
made false (`still_reproduces: false` with a verifying scan), re-bless manifests, regen. The
Cross-repo note names the engine PR. `bias-history.yml` regenerates the chart on merge.

## Done criterion

The module row is `stated`; `signal_contract_audit.py --ci` exits 0 with a smaller baseline;
the bias report's open-defect share for the metrics this signal feeds did not rise; every red
cell that remains on this signal is `inherency` or `echo` in the report's cause table.
