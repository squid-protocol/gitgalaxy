---
description: "Three draft contracts of the keyword-family validity epic (#8863 / #8862) declared: debug_prints, sync_locks, concurrency -- sentence, measured incidence, contradictions listed."
---
# The `debug_prints`, `sync_locks` and `concurrency` contracts, declared (#8862)

Part of #8863 (keyword-family validity). These were three of the seven unplanted `draft` rows
(`docs/domain_sensor_contracts.md` left them for a later pass). They move to **`declared`**, the
state #2897 defined for rows with no keyword-rosetta plant: the sentence, `kind` and `unit` are
fixed and language-independent; the sentence is contained verbatim in the `# key:` comment of
`gitgalaxy/standards/how_to_add_a_language.md` (the audit's containment check); incidence was
measured on both corpora; every rule that contradicts the sentence is **listed, not fixed**.
No rule is edited, so no corpus cell moves and nothing is re-blessed.

## The sentences

All three are `kind = site` (unit: sites). The sentence is what the family-validity oracles
(`tests/tools/family_oracle*.py`) are scored against.

| signal | contract |
|---|---|
| `debug_prints` | A site that writes text to the console or a diagnostic stream for a developer to read while the program runs -- a print, echo, dump or trace call -- in its own call or statement form; output addressed to a file or writer, and structured logging (telemetry), are not sites |
| `sync_locks` | A site that acquires, releases or wraps a mutual-exclusion or atomic-ordering primitive so that threaded code does not race -- a lock or unlock call, a mutex, semaphore or synchronized region, an atomic operation -- in its own invocation form |
| `concurrency` | A site that starts, schedules, awaits or hands off work to run concurrently with its caller -- an async or await keyword, a task, thread, goroutine or promise constructor, an executor or timer submission -- in its own keyword or call form |

Readings this settles from the #8868 table (a reading of the existing words, not a new
definition; the maintainer can overrule it by editing the sentence):

1. **A write to a writer is not a `debug_prints` site** (`fmt.Fprintf(w, ...)`, `fprintf(out, ...)`):
   the output is addressed to a file or stream the program owns, which is the program's product,
   not a developer's console. This matches the correction posted on #8868 for Go.
2. **`concurrency` and `sync_locks` are separate keys** (`how_to_add_a_language.md` rule 8): starting
   or awaiting work is `concurrency`; a lock, mutex, semaphore or atomic operation is `sync_locks`.
   An atomic *store* is `sync_locks`; spawning the task that performs it is `concurrency`.
3. **Ruled by the owner (2026-11-24, comment on #8862):**
   - **`assert` is not an abort** for `panics_and_aborts`: it is a check, not a statement that ends the execution context.
     A language rule that counts it (Lua) is a rule bug; if assertions are wanted they become their own family.
   - **`doc` is the structured form each language's tools read** (docstring, `///`, `/** */`, a Go declaration comment).
     A language with no such form is N/A for `doc`, never "any comment"; TS/JS counting any comment is a rule bug.
     Both fixes are tracked under #8863 and are not made here.

## What was measured

`tests/tools/rule_probe.py <rule> all` over the Prism code stream (comments stripped, string
literals kept, the text `detector.py` hands the rule). Crucible = `language-crucible` v1.8.0,
rosetta = `keyword-rosetta` main (`2e67433`). 79 language definitions; "defined" counts those
that carry a rule (the rest record `None`, a contract-level absence).

| signal | defined / None | crucible hits | rosetta hits | densest language: top token |
|---|---|---|---|---|
| `debug_prints` | 56 / 23 | 8021 | 18 | `fortran` 26.7/file `print`; `matlab` 25.7/file `fprintf`; `scheme` 12.4/file `newline` |
| `sync_locks` | 53 / 26 | 1227 | 5 | `go` 10.9/file `Lock`; `scala` `synchronized`; `zig` `lock`; `agc_assembly` `INHINT` |
| `concurrency` | 53 / 26 | 4331 | 2 | `typescript` 21.4/file `Promise`; `swift` `async`; `dart` `Timer`; `agc_assembly` `ENDOFJOB` |

## Contradictions found (listed, not fixed)

| signal | language | what the rule counts | reads the sentence? |
|---|---|---|---|
| `debug_prints` | c, matlab | `fprintf(out, ...)` / `fprintf(sql, ...)`: output to a file handle | no: reading 1 excludes a write to a file or writer; only the bare console form counts |
| `debug_prints` | ada, scheme | `New_Line` and `(newline p)`: a line break on a file or port, not a message | no |
| `debug_prints` | crystal | `pp` as a variable name (`pp.list(...)`, `def pretty_print(pp)`) | no: an identifier, not a call to the printer |
| `debug_prints` | dockerfile | `echo` inside a `$(...)` command substitution that builds a value | no: not output to a console |
| `debug_prints` | erlang | `io:format()` inside a `-spec` type annotation | no: a type reference |
| `debug_prints` | assembly | `call printf` in a comment-trailing instruction | partly: a real call, but a C-library call from a listing |
| `debug_prints` | go | `print("\n")` inside string content | no: stream contract, a keyword in a string literal counts (#2535) |
| `sync_locks` | dart | `Completer` (a future's completion handle) | no: not mutual exclusion |
| `sync_locks` | rust | `semaphore` as a method or variable name (`semaphore.is_closed()`) | partly: a semaphore query is not an acquire or release |
| `sync_locks` | php | `'wp-remove-post-lock'`: a string literal | no |
| `sync_locks` | agc_assembly | `INHINT` / `RELINT` (interrupt inhibit and release) | design question: it is the platform's only exclusion primitive; reads the sentence in spirit |
| `concurrency` | agc_assembly | `ENDOFJOB` (end of a scheduled job) | design question: the executive's job scheduling is hand-off to a scheduler |
| `concurrency` | dart | `import 'dart:async'` and `Timer` (a delayed callback) | partly: the import is not a site; a timer submission is |
| `concurrency` | zig | `@atomicStore` | no: an atomic operation is `sync_locks` (reading 2), a dual with that family |

`tests/family_validity_baseline.json` carries the parser-oracle scores for the families that have an
oracle; none exists yet for these three (they are callee lists, so the oracle would be a second
reading of this sentence, not independent proof).

## What this does not do

- It edits no rule and writes no ledger entry; each contradiction above is a one-layer rule fix
  that can land with its own timing.
- It does not touch the four other unplanted drafts (`dead_code`, `reflection_metaprogramming`,
  `spec_exposure`, `llm_api`) or the five planted ones (`safety_bypasses`, `doc`, `telemetry`,
  `planned_debt`, `fragile_debt`), which need the full family audit.

## Reproducing the measurement

```sh
export LANGUAGE_CRUCIBLE_PATH=<clean language-crucible v1.8.0> KEYWORD_ROSETTA_PATH=<keyword-rosetta main>
python tests/tools/rule_probe.py debug_prints all --samples 3 --json /tmp/debug_prints.json
python tests/tools/rule_probe.py sync_locks all --samples 3
python tests/tools/rule_probe.py concurrency all --samples 3
```
