---
name: llm-language-review
description: The standard method for validating a language's extraction with blind LLM readers -- roles, the nine steps, the reviewer prompt, how to rule a disagreement, what you may claim from the result, and the traps found so far. Use when starting or extending a review of any language (COBOL, PL/I, JCL, BMS, CSD, or a new one), when someone asks "how thorough is X", or before dispatching reviewer agents. The mechanics for the mainframe keys live in `mainframe-ground-truth`; this skill is the language-independent protocol around them.
---

# Reviewing a language with blind LLM readers

**What this method is.** Our engine reads source and reports facts (units, calls, copybooks, data moves, DSNs, ...).
An *answer key* is a second, independent reading of the same source. *Blind reviewers* are fresh LLM instances that
read the source with no sight of the key or the engine. We compare all three, and a person (or the session) rules on
every disagreement **from the source**.

**What it is not.** It is not proof and not a human sign-off. It measures the key and the engine against an independent
reading, with a bound on the error rate of what was sampled. Its real value is the one thing the engine-versus-key
check cannot see: **a defect the engine and the key share.** (`SET ROUTINE TO ENTRY 'X'` read as an `ENTRY`
statement by both: the ledger was silent, a blind reader found it.)

Mechanics (commands, files, ledger, tiers): `.claude/skills/mainframe-ground-truth/SKILL.md`. Evidence wording:
`.claude/rules/mainframe-evidence-policy.md`.

## Roles (keep them separate)

| role | who | must never |
|---|---|---|
| Engine | the code under test | be an input to the key or to a reviewer |
| Key reader | our own reader, written from the contract (`cobol_answer_key.py`) | import the engine; be edited by hand to match it |
| Reviewer | a fresh-context agent per batch, same model family is acceptable, a different family is stronger | see the key, `truth.json`, the ledger, tests or the tools |
| Judge | the session or a person | rule from a reviewer's say-so: always from the source |

## The nine steps

1. **Write the contract first.** For each fact: what counts, how it is spelled (the canonical string), what is out
   (comments, sequence fields, generated copies, `%` preprocessor lines), and every normalisation. The reviewer brief is
   generated from this. *A disagreement caused by something the contract never said is a contract bug, not a reviewer
   bug* (see "Contract gaps").
2. **Draft the key with the independent reader.** Every entry starts `draft`. Never seed it from engine output.
3. **Choose the scope.** Small section: ask every file, in full (empty files too: that is the recall check). Large
   section: a seeded, stratified sample (rare constructs first, then random windows that may hold nothing). Write the
   seed and the strata into the key. *Leave out* sources with no balanced reading (a cut-down file, `%INCLUDE`
   fragments) and generated copies (`.expanded/`, any dot-directory); record the excluded list.
4. **Cut batches.** About 70 key facts per batch (`--max-items 70`). Stage a clean copy of the source for the reviewers
   (`--stage`): no `.git`, no dot-directories, no key. Cut costs nothing: look at the batch count and the size first.
5. **Dispatch blind reviewers** with the standard prompt below. One agent per suite group is fine (it handles that
   group's batches in turn). At most 20 agents at once.
6. **Grade.** `grade` compares canonical fact sets per batch and lists every disagreement as key-only or
   reviewer-only. Nothing is decided yet.
7. **Rule every disagreement from the source** (decision table below). A `rulings.json` entry needs a verdict and a
   `why` that names the source line.
8. **Fix what is real**, in the same PR: the key reader *and* the engine if both had it, a test that pins the shape,
   `ground_truth_ledger.py update`, `field_testing.py report --write`, and a golden bless if a fixture moves
   (`golden-master-guidelines.md`). Log the defect (field-testing protocol). Redraft the key with the tool's own command.
9. **Sign and report.** `sign` records the batch, the reviewer string, the counts and the 95% upper bound. Quote the
   result only as the generated report words it (below).

## The standard reviewer prompt

Send exactly this, with the batch directory filled in. It is deliberately short: the brief carries the contract.

> You are an independent blind reviewer. Read `<batch>/brief.md` and do exactly what it says, reading the source files
> it names. Write your final JSON object (only the JSON, in exactly the format the brief asks for) to
> `<batch>/answers.json` with the Write tool. Do NOT open any other file in the batch directory (never `truth.json`),
> never look for or read any answer key, ground-truth ledger, analysis tool or test, and only read source files under the
> repository root named in the brief. Only list facts whose statement STARTS inside the window you were given.
> Treat commented-out text as no code. Read the code; do not answer from a grep or a script you wrote unless the brief
> says the section is mechanical. Reply with just "done" and a count per batch.

Ask the reviewer to say *how* it produced the answers (read / grep / script). Several said so unprompted today; make it
a field so it is recorded (see "Tooling gaps").

## Ruling a disagreement: the decision table

Read the cited line and its neighbours first. Then:

| what you find | verdict | action |
|---|---|---|
| The reviewer left a plain statement out, or mis-copied a name | `key_correct` | none; counts toward reviewer error |
| The reviewer answered outside its window (a statement that starts between two windows) | `key_correct` | none |
| The "code" the reviewer read is inside a comment (`/* ... */` that does not nest) | `key_correct` | none |
| The reviewer read a comment as a parameter (`DYNAMNBR=20 ,COND=(4,LT)`: a blank ends the JCL operand field) | `key_correct` | none |
| The source is silent and the contract is silent (user function call, DSN member, children without a CSD) | `key_correct` *and* a contract note | write the rule into the contract and the brief; if it changes meaning, file an issue (#9230) |
| The key is wrong (`USAGE NATIONAL` not read) | `key_fixed` | fix the reader, redraft, test; `sign` re-checks the current key |
| **Key and engine both wrong, so they agreed** | `key_fixed` | fix both; this is the finding the method exists for |
| Hundreds of disagreements, one pattern, one file set | **stop** | it is a plan bug, not a result (windows inside `.expanded/` copies: 128 and 44 false rows) |

Never mark a real defect `deliberate` to make the ledger green. If a disagreement is a *design* question (do header
comments belong to the unit above or below), say so in the cause text and leave it open.

Expect most disagreements to be the reviewer's or the contract's. Today: about two dozen in round 1 and 54 in round 2,
of which 1 and 3 were key errors. So every disagreement still needs the source read; do not skip it because "it is usually the
reviewer".

## What you may claim

- State the tier and the bound from the generated report: *"sample_verified: 0 key errors in N asked, at most X% at 95%
  (LLM readers, no human sign-off)."* The bound is for the **sampled** facts only.
- Say *"LLM-reviewed"*, never *"proven"* or *"verified"* alone. Do not say "field-tested" for a field the report calls
  open.
- A reviewer that grepped or scripted gives weaker evidence for *presence*; an "all clear" from grep is acceptable for
  "this construct does not occur", not for "these N rows are right". Say which batches were read and which were scripted.
- Engine-versus-key agreement is not evidence of correctness. Only the blind reading is.
- Record, for the sheet's `llm-read` method: model id, the brief's hash, and the sample rule and seed.

## Traps found so far

1. **A plan freezes once batches exist.** To widen, extend it from files no earlier window looked at; keep the reviewed
   files. Never re-draw (the first PL/I 25 files stayed; 125 were added).
2. **The census listed generated copies** (`.expanded/`). They made 172 false disagreements before anyone looked.
   Every file listing now skips dot-directories, and the staged copy omits them.
3. **`truth.json` sits next to `brief.md`.** Reviewers saw it listed. They did not open it, but a reviewer could. Stage
   the reviewer directory with the brief only.
4. **A reviewer answers a different shape than the schema** (a list where `{"moves": [...]}` was asked). Fix the shape
   mechanically and keep the original; never change content.
5. **Concurrency cap.** 20 agents at once; send the rest as slots free up.
6. **Ledger and goldens are generated.** After a merge take main's side, rerun `update`, re-bless on the *merged* engine.
7. **A CI flake is not a result.** A Maven download failure and a Java porting test both failed unrelated to the change;
   read the log, then rerun only the failed job.
8. **Never use `git stash` in this repo** (the session's permission layer will refuse it, correctly).

## How many rounds

- **One full round per field per corpus.** A second round on the *same* fields found 2 real defects in about 54 batches
  across both rounds: the cost is moderate, the yield low.
- Run again when something changes: a new corpus, a new construct class, an engine change that touches the field, or a
  new language.
- The best use of the next reviewer is on **shapes we have not read**: a hand-built hard-case corpus (the traps in
  `mainframe-ground-truth`), a different style of shop, or a different model family via `agy`.
- Field-tested needs fresh rounds: the stopping rule is in the field-testing protocol.

## Applying it to another language

The pieces that are language-independent: the roles, the contract-first rule, the prompt, the decision table, the
claims rules. The pieces that are COBOL-shaped today: the key reader, the canonical strings, the suites. For a new
language:

1. Pick the independent reader: an exact parser or tree-sitter grammar if one exists (method `exact-parser` /
   `tree-sitter` on the sheet), else write a small reader from the contract (method `answer-key`).
2. Write the contract and canonical strings for 2-3 fact channels (units, calls, imports first).
3. Add a `draft` / `add-*` command and a `cross_verify`-style `census` / `grade` / `sign` for it; reuse the batch format.
4. Run the nine steps. If no reader can be built, the method is plain `llm-read` and the sheet says so.

## Checklists

**Before dispatch:** contract written; key drafted; excluded sources recorded; batch count and size known; staged copy has
no dot-directories and no key; prompt filled in; ≤20 agents.

**After grading:** one pattern across many disagreements? stop and check the plan. Every remaining row read in source.
Reviewer method noted per batch.

**Before the PR:** reader and engine fixed together; a test per fixed shape; `update` and `check` clean; field-testing
report regenerated; goldens re-blessed on the merged engine if a fixture moved; PR body states counts, the claims in the
words above, and which batches were scripted.

## Tooling gaps (not done yet)

- Move `truth.json` out of the reviewer-visible batch directory.
- Make "how I produced this" a required field of `answers.json`; record it at `sign`.
- Record the model id and brief hash at `sign` (today `--by` is free text).
- Flag out-of-window answers automatically instead of listing them as disagreements.
- Report a per-batch reviewer-error rate, so a plan bug stands out.
- Extend the key / census tooling beyond COBOL-family sources.
