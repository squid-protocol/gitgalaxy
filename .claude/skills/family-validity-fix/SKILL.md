---
name: family-validity-fix
description: Work one language's red cells in the keyword-family validity grid (epic #8863) -- re-measure each cell, decide whether the rule, the oracle or the contract is wrong, fix the smallest thing, prove it with the oracle, CPU time, keyword-rosetta and a clean-venv golden bless, and open one draft PR. Use when the user or churn says "work the <lang> red squares", "fix <lang> keyword families", picks up a `- [ ] **<lang>**` line on #8863, or a #8868-style per-language difference. NOT for adding a language (add-language), a new family (add-signal), or the oracle for a language that has none (extend tests/tools/family_oracle_ts.py first).
---

# Fix one language's red keyword-family cells

A cell is red when the weaker of recall and precision is under 0.8 on at least 10 oracle functions
(`python tests/tools/family_red_cells.py --lang <lang>`). **One language per PR.** The reference page
`docs/agents/family-validity-checklist.md` holds the rulings, the cause table, the recipes and the PR checklist; read it first.

## The loop, per cell

1. **Re-measure on current `origin/main` before touching anything.** About half of what the list says is already fixed or was never
   the engine's. Use the pinned crucible for numbers you will quote (`family_oracle_sweep.py`); a real repository
   (`/nvme-data/gitgalaxy-data/<repo>`) is for triage only.
2. **Name the cause class** (table in the checklist page): oracle too broad, oracle misses a form, the rule counts another
   construct, a named construct is missing, or the contract is silent. Say which in the PR.
3. **Read the contract** (`signal_contracts.py`, `docs/<family>_rule_contract.md`) and the rulings already made. If it answers
   the question, apply it. If it is draft, silent or contradictory: file the question on #8863 with the numbers, and **move to the
   next cell**. Never wait for the owner and never pick a reading that moves a count without a ruling.
4. **Trace before you edit.** Find the functions where family and oracle disagree and read the actual lines. Do not infer the cause
   from the numbers: Go `closures` looked like "lambdas missed" and was method declarations; C `panics` looked like `assert` and
   was `return -1`; Rust `exit` looked like missing process exits and was `span.exit()`.
5. **Fix the smallest thing.** A wrong oracle is fixed in `tests/tools/family_oracle.py` (Python) or `family_oracle_ts.py`
   (everything else), with a comment citing the contract. A wrong rule is fixed in
   `gitgalaxy/standards/language_standards/languages/<lang>.py`, with a comment citing the issue. Prefer narrowing a rule to
   an operative form over deleting it; prefer anchoring on what must be next to the match over a longer alternation.
6. **Test both directions.** Add cases to a test beside the rule: the forms that must count and the false-positive forms that
   motivated the change (`tests/test_batch_b_rules.py` is the shape).
7. **Re-score** the cell. It must move toward 0.8 and nothing else in that language may fall; read the whole language's rows, not
   one.

## Then, once for the PR

8. **CPU**: three alternating runs base vs branch on `<crucible>/data/<lang>`, mean `user` seconds. Not worse beyond noise.
9. **keyword-rosetta**: dry-run or `verify_language.py` for this language (checklist page). Moves mean `rosetta:rebless-owed`.
10. **Goldens**: `crucible_check.py --update --yes` in clean venvs, and **attribute the diff**: unmodified `origin/main` blesses to
    zero changed files, and the file-level differences are this language's (knock-ons are listed in the checklist page).
11. **Open a draft PR** with the checklist filled in, "Part of #8863". Heavy CI skips drafts (#5104): the owner or churn marks it
    ready; if checks stay skipped after that, push an empty commit.
12. **If main moved and the fixtures conflict**: merge `origin/main`, take main's golden directories, re-bless
    (checklist page). Never stack a second PR on a language file that has an open PR.

## Do not
- change a family to match an oracle you have not checked against the contract
- touch more than one language, or a family outside the red list, in one PR (note it as "not in this PR" instead)
- quote a number from an unpinned repository, or a cell under 10 functions
- hand-edit a golden fixture, `git stash` in the repo, or reuse a venv whose editable install points at another checkout
  (`PYTHONPATH=<worktree>` for scans; clean venvs for blessing)
- leave a surprise unreported: a family that fell, a language that moved that you did not touch, a rosetta cell that shifted

## Report back
Per cell: before and after (recall / precision, functions), the cause class, and what you left. Plus CPU, rosetta, bless
attribution, and the PR link. Plain words: say what each rule now counts.
