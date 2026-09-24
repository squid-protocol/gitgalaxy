---
name: mainframe-ground-truth
description: Work with the mainframe ground-truth system -- the hand-verified COBOL answer keys (tests/cobol_mainframe/answer_key/), the ground-truth ledger CI gate (tests/tools/ground_truth_ledger.py, mainframe-ground-truth.yml), and blind LLM cross-verification / census (tests/tools/cross_verify.py). Use when the ledger fails in CI ("NEW mismatch", "no longer reproduces", "UNTRIAGED", "scoreboard differs"), when adding a corpus or an answer-key section, when running or grading a blind review or census, when a snapshot or ledger conflicts after a squash merge, or when the user asks "how accurate is the COBOL extraction". Not for writing the extractor itself (add-fact-channel) or forge/refractor behaviour (cobol-modernization).
---

**The answer key is the oracle. Neither the engine nor the forge is.** Every claim about COBOL
extraction accuracy comes from the ledger's scoreboard, never from "the output looks right".

## The pieces

| piece | what it is |
|---|---|
| `tests/cobol_mainframe/corpora.json` | the pinned corpora (zopeneditor, CBSA, CardDemo); each names its key |
| `tests/cobol_mainframe/answer_key/<corpus>.json` | per-program truth. `verification.tier` is `llm_verified` < `cross_verified` < `human_signed`, and `verification.census` marks a program read twice, blind |
| `tests/tools/cobol_answer_key.py` | the key's **own** reader (draft / add-* / score / sample). It never imports the engine or the forge; a runtime test enforces this |
| `tests/tools/ground_truth_ledger.py` + `ground_truth_ledger.json` | every engine/forge disagreement with the key → cause → kind (`defect` or `deliberate`) → issue |
| `tests/tools/cross_verify.py` | blind second reviewer: `brief` / `census` → `grade` → `sign`, plus `coverage` |
| `tests/tools/cross_verify_sections.py` | the same blind census for the per-file fact-channel sections (SQL access, CICS tasks, MQ, units of work, job submissions, TD triggers): every COBOL file asked, empty ones too; signing sets each section's `*_validated` flag and `cross_verified` tier |
| `.github/workflows/mainframe-ground-truth.yml` | every PR: fetch, scan, score and `check`; also runs `tests/cobol_mainframe/` with the corpora present |
| `.github/workflows/answer-key-guard.yml` | flags PRs that change a key or the ledger, with a semantic diff of what moved |

Environment: `GITGALAXY_MAINFRAME_CORPORA=<main checkout>/.mainframe_corpora` (it's shared
across worktrees; fetch once with `mainframe_corpus.py fetch`) and
`GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER`. Scans are cached per engine commit plus a dirty hash,
so a re-check on an unchanged engine takes seconds.

## A ledger failure in CI: triage

```sh
python tests/tools/ground_truth_ledger.py check          # what CI runs
```

- **`NEW mismatch`** means your change moved an engine or forge answer away from the key. Find out whether it's a regression or the key being wrong: **read the source**. If it's a regression, fix it. If the key is wrong, fix the key (and its reader, with a test), then re-census that program.
- **`no longer reproduces`** means you fixed something. Ratchet it in with `update`. That's the point of the gate: improvements get locked in.
- **`UNTRIAGED` after `update`**: `assign CAUSE 'corpus :: side | field | * | fp'` with `--kind defect --issue N` (something to fix) or `--kind deliberate --issue N` (by design; the issue records the decision). **Never mark a defect deliberate to get green.** The kind is visible in every report.
- **`cause … is used by no mismatch`**: `update` drops it, or it happened because a merge kept a cause that both sides emptied.

## Merging and rebasing: the ledger and snapshots are generated

After a sibling PR squash-merges, the ledger, `refraction_snapshot/**` and golden masters
conflict:
1. Take **main's side** of every generated file: `git checkout --theirs` for a merge.
2. Re-run `ground_truth_ledger.py update`. **Re-apply your cause assignments**, because main's ledger doesn't have them; `check` shows them as `UNTRIAGED`.
3. Regenerate snapshots with `refraction_snapshot.py update --excerpts` and `--corpus <name>`, and golden masters with `crucible_check.py --update --yes`.
4. Scope against **main**, not HEAD. After a merge, `bless_scope.py --from-head` compares against your own pre-merge commit. Instead: `golden_store.py export --rev origin/main <fixture> /tmp/m.json`, then `bless_scope.py /tmp/m.json <fixture>`.
5. For test files that both PRs appended to, **rebuild from main plus your block**. Don't regex conflict markers: the repo's `# =====` comment banners look like `=======`.

## Blessing a refraction snapshot

Run `refraction_snapshot.py check` first and **read the diff**. Every moved line must trace to your change. Known shapes:
- A column removed and re-added in the same file is just a trailing-comma move.
- An entity rename follows the forge's "table named after the last 01 group" rule.
- A type change can be a latent bug surfacing: `PIC 9(4).` used to include the period and type as DECIMAL.

Say what moved, and why, in the PR.

## Adding an answer-key section (a new channel under epic #3445)

1. Write an **independent** reader in `cobol_answer_key.py`: raw source, the key's own `Source`, no gitgalaxy import. Add an `add-<thing>` subcommand that leaves every other section and every signed-off entry untouched.
2. Draft it for all three corpora. Start the section's sign-off flag at `false` (`<x>_validated`), and list the flag in `ground_truth_ledger.TRUTH_FLAGS`.
3. Add the scored field in `score()`, and run `ground_truth_ledger.py update` and `assign`.
4. **Check it yourself** against the source: every disagreement between the key, the engine and the forge.
5. **Census it** (below), then set the flag.

## Blind review and census

```sh
python tests/tools/cross_verify.py census --corpus <c> --out <dir> --stage <dir>/src   # every program, ~150 units a batch
python tests/tools/cross_verify.py grade  --corpus <c> --dir <dir>/<c>/batch_NN
#   settle each disagreement against the source; <dir>/.../rulings.json
python tests/tools/cross_verify.py sign   --corpus <c> --dir <dir>/<c>/batch_NN --by "<reviewer>"
python tests/tools/cross_verify.py coverage --corpus <c>        # must reach 100%
```

- **Reviewer.** Give a fresh-context agent **only** `brief.md` plus the staged source path. **Always `--stage`**: a brief pointing inside `/nvme-data/projects/gitgalaxy/…` contradicts its own "don't read gitgalaxy" rule, and the reviewer's reads get denied. One reviewer per batch, run in parallel.
- **Cross-family reviewer.** Gemini through `agy -p "$(cat brief.md)" --dangerously-skip-permissions …` is stronger evidence, but the auto-mode classifier blocks Claude from launching it. The user has to run it or allow it. Never route around that block.
- **Rulings.** Rule `key_fixed` (the key was wrong: fix it and its reader, with a test) or `key_correct` (the reviewer was wrong, with the source evidence). `sign` refuses while anything is unruled or a `key_fixed` item still disagrees.
- **Structural reachability.** Reachability is **structural**: every condition may go either way, with no value analysis. A reviewer's data-flow argument is `key_correct` (the INQACCCU AH999 precedent).
- **Grader normalisations**, which are not key errors: CICS program names are blank-padded to 8 (`'INQCUST '`); a subscripted table operand (`X(WS-OPTION)`) is the table `X`.
- **Section census.** `cross_verify_sections.py census --corpus <c> --out <dir> --stage <dir>/src`, one reviewer per batch, then `grade` / `sign` / `coverage`. Before spending reviewers, prove the canonical forms round-trip: a reviewer built from the key's own rows must grade 0 disagreements. Reviewer slips seen so far and how they were handled: a null `verb` on a kind that fixes it (normalised in the grader), a value shifted into the next field and a brief placeholder copied literally (both ruled `key_correct` with the source line). Word the brief's templates with `<angle>` placeholders.
- **Suites.** `--suite channels` (default) is the six #3445 channel sections over every COBOL source; `--suite files` is file control, VSAM defines and JCL job flow over every COBOL program and JCL member. `coverage --suite files` reports it separately.
- **A reviewer can be right.** The files census found a real reader bug that engine and key shared: a `//*` comment inside a continued JCL statement (BUILDONL.prc) ended the statement in both. Rule it `key_fixed`, fix both readers with a test, refresh the key, then `sign`, which re-grades against the current key.
- **Census gate.** `test_small_corpus_keys_are_fully_censused` fails for any program lacking `verification.census`. Small corpora are censused; for a corpus too large to census, use sampled confidence (rule of three, reset per category on each `key_fixed`) and add a matching gate.

## COBOL reader traps that have bitten every reader (the key's, the forge's and the engine's)

- **`\b` before a verb matches after a hyphen.** `END-IF`, `END-PERFORM`, `END-CALL` and `X-CALL` read as `IF`, `PERFORM` and `CALL`. Use `(?<![A-Z0-9-])`. The engine has a registry-wide guard for this: `_hyphenated_words`.
- **Sequence areas.** Cols 1–6 on the *next* line (`002600     NAME.`), cols 73–80 on the same line, digit-only blank lines, and `R2` change markers. A COBOL word contains a letter; a digit-only token is a sequence number.
- **A period on the next line.** Paragraph headers, COPY statements, REPLACING clauses.
- **Any unconditional terminal sentence ends a unit**, not only the last one. `ALTER P TO PROCEED TO Q` makes Q a GO TO target.
- **A literal is data except where it names a callee.** `CALL 'X'` is a callee (the engine's `_calls_out_literal_callee`); `DISPLAY 'CALL X'` is not.
- **A data-only copybook that another program copies is a dependency, not a data dump.** The #3417 auditor exemption applies.
