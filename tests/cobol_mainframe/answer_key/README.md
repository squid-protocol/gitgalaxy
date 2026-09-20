# COBOL modernization answer key (#3210)

Hand-verified, per-program truth for real mainframe source. It is the fixed point that the refraction ("forge") tools in `gitgalaxy/tools/cobol_to_cobol/` and the engine's master DB are both measured against.

Neither parser is the oracle for the other. Before this key existed, every question of "which one is right" meant reading source by hand (see `docs/refraction_engine_differential.md`).

| file | corpus | pinned ref | programs | units | dead (non-trivial) |
|---|---|---|---|---|---|
| `zopeneditor-sample.json` | [IBM/zopeneditor-sample](https://github.com/IBM/zopeneditor-sample) | `8f983530` | 5 | 58 | 0 (0) |
| `cics-banking-sample-application-cbsa.json` | [cicsdev/cics-banking-sample-application-cbsa](https://github.com/cicsdev/cics-banking-sample-application-cbsa), branch `July2024Refresh` (its `main` was emptied at the 2024 sunset) | `41733453` | 31 | 680 | 62 (10) |

## What each program records

| field | content |
|---|---|
| `program_id` | the PROGRAM-ID |
| `units` | real paragraph and section headers (Area A of the PROCEDURE DIVISION): name, kind, line |
| `dead` | units unreachable from the entry, each with a `reason`. `trivial: true` marks an `EXIT.`-only paragraph: dead, but carrying no logic |
| `copybooks` | every `COPY` / `EXEC SQL INCLUDE`, with the library (`IN MYLIB`), `resolves_to` (a member path, never a program) or `null` plus `why` (CICS-, LE- or DB2-supplied; BMS-generated symbolic map) |
| `files` | `SELECT … ASSIGN`: internal name, DD, and the OPEN modes actually used (a multi-mode OPEN is split per keyword) |
| `calls` | `CALL` and `EXEC CICS LINK/XCTL PROGRAM(…)`: literal or identifier, the target (through the working-storage `VALUE` for an identifier), and the program it resolves to |
| `cics`, `sql` | presence of `EXEC CICS` / `EXEC SQL` |
| `verification` | `status: validated`, who, when, and program-specific notes |

The top-level `method` block records how each field was verified.

## Authority

`tests/tools/cobol_answer_key.py draft` computes **candidate** values with its own fixed-format reading. It handles:
- Area A headers
- PERFORM … THRU ranges, GO TO, and SECTION fall-through
- unconditional terminals, including a PERFORM of a section that never returns
- `EXEC CICS HANDLE ABEND/CONDITION/AID` labels
- `zapp.yaml` copybook libraries

The draft is a helper; the verification is what makes it the key:
- Every dead verdict was checked against the source.
- Every value where the draft, the forge and the engine disagreed was resolved against the source.
- A sample of live-unit reach paths was checked.

Four draft errors found that way are now pinned by `tests/cobol_mainframe/test_cobol_answer_key.py`:
- abend handlers registered with `HANDLE ABEND LABEL` read as dead;
- fall-through past `PERFORM GET-ME-OUT-OF-HERE`;
- `AUTHOR. James O'Grady.` opening a literal that hid the rest of the file;
- a shared PROGRAM-ID resolving across workspace roots.

A key whose programs are `draft` is not evidence. `test_key_integrity` fails on one.

## Commands

The corpora are not vendored. `tests/cobol_mainframe/corpora.json` pins them, and `tests/tools/mainframe_corpus.py` fetches, scans and scores them (#3213):

```sh
# fetch every pinned corpus, scan it (cached per engine commit), score forge + engine DB
python tests/tools/mainframe_corpus.py fetch
python tests/tools/mainframe_corpus.py score [<corpus> ...] [--md out.md]

# the same score by hand, for a clone or DB outside the manifest
python tests/tools/cobol_answer_key.py score <clone> --key tests/cobol_mainframe/answer_key/<corpus>.json \
    --db <scan>/<corpus>_galaxy_master.db [--md out.md] [--json out.json]

# regenerate a draft (then re-verify before replacing a committed key)
python tests/tools/cobol_answer_key.py draft <clone> --corpus <name> --url <url> --ref <sha> \
    --out draft.json --report reach_paths.md
```

The `draft` of each committed key reproduces its program data exactly, minus the `verification` blocks.

## Scores at #3210 (engine `44ffeb1e`)

P = correct / reported, R = correct / true, over (program, value) pairs.

**cics-banking-sample-application-cbsa**

| field | forge | engine DB |
|---|---|---|
| program_id | P 31/31 · R 31/31 | P 31/31 · R 31/31 |
| units | P 452/729 · R 452/680 | P 680/706 · R 680/680 |
| dead | P 57/623 · R 57/62 | P 29/248 · R 29/62 |
| dead (non-trivial) | P 5/571 · R 5/10 | P 2/221 · R 2/10 |
| copybook paths | P 0/29 · R 0/114 | P 78/78 · R 78/114 |
| DD names | P 1/1 · R 1/1 | not carried |
| outputs | P 0/0 · R 0/1 | not carried |
| cics/sql | P 42/42 · R 42/42 | not carried |

**zopeneditor-sample**

| field | forge | engine DB |
|---|---|---|
| program_id | P 5/5 · R 5/5 | P 5/5 · R 5/5 |
| units | P 58/75 · R 58/58 | P 58/67 · R 58/58 |
| dead | P 0/17 · R 0/0 | P 0/5 · R 0/0 |
| copybook paths | P 0/0 · R 0/14 | P 2/2 · R 2/14 |
| DD names | P 12/12 · R 12/12 | not carried |
| inputs | P 6/12 · R 6/6 | not carried |
| outputs | P 0/0 · R 0/6 | not carried |
| dynamic CALLs | P 3/3 · R 3/3 | not carried |

What the scores say, with the issue that owns each:

- **Dead code.** Neither side is usable yet. CBSA has 10 units of real dead logic: `CALC-DAY-OF-WEEK` and four `POPULATE-TIME-DATE` sections, with their first paragraphs.
  - The forge finds 5 of the 10 among 571 claims (#3203).
  - The engine's `usage_status` finds 2 among 221 (#3198).
- **Copybooks.**
  - The engine is always right when it draws an edge (78/78), but draws only 68% of them, because ambiguous targets are dropped (#3199). It also has no view of `zapp.yaml` libraries.
  - The forge resolves 0 real copybooks (#3203).
- **Outputs.** The forge reports none, on either corpus (#3204). On BANKDATA even the single-mode `OPEN OUTPUT` is lost. The forge marks the entry paragraph `A010` itself dead, because the programs it inlines as copybooks shift which paragraph comes first (#3203), and that masks the OPEN. With no dead list, the lineage tool finds the `VSAM` output.
- **Units.** The engine's recall is complete. Its extra units are the Area-B continuation phantoms (#3197).

## Update: engine lineage and call graph (#3200 / #3201), 2026-09-20

Every field the engine column reported as `not carried` is now carried, and
exact. Also adds a new scored field, `call targets`.

**cics-banking-sample-application-cbsa**

| field | forge | engine DB |
|---|---|---|
| DD names | P 1/1 · R 1/1 | P 1/1 · R 1/1 |
| outputs | P 1/1 · R 1/1 | P 1/1 · R 1/1 |
| call targets | n/a | P 45/45 · R 45/45 |

**zopeneditor-sample**

| field | forge | engine DB |
|---|---|---|
| DD names | P 12/12 · R 12/12 | P 12/12 · R 12/12 |
| inputs | P 6/6 · R 6/6 | P 6/6 · R 6/6 |
| outputs | P 6/6 · R 6/6 | P 6/6 · R 6/6 |
| dynamic CALLs | P 3/3 · R 3/3 | P 3/3 · R 3/3 |
| call targets | n/a | P 3/3 · R 3/3 |

`call targets` is every program name a call site denotes — a literal, or an
identifier read through its working-storage `VALUE` clause. It has **no forge
column**: the DAG architect records only non-literal `CALL` operands and never
sees `EXEC CICS LINK`/`XCTL`, which is 140 of CBSA's 144 call sites.

Before any of this was wired into the engine, the extractor was scored directly
against the key's `calls` and `files` blocks: **147/147 call sites** match on
verb, form, operand, target *and line*, and **13/13 dataset records** match on
internal name, DD and modes, with no false positives on either corpus.

The `calls` field is now a first-class scoring target rather than key-only data.
Note what it measures and what it does not: `resolves_to` is compared only
through `call targets`' name set, because which of two files sharing a
PROGRAM-ID a call binds to is a link-edit-order question the key answers with
"nearest" and the engine reproduces — not an independent check.
