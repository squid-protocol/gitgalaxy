---
description: "Ratification ledger for the keyword-family oracle (#8863 / #8862): each family's contract sentence beside the Python oracle's reading, with a verdict and the open owner questions."
---
# Oracle readings against the contracts (#8862, part of #8863)

The validity tool (`tests/tools/family_oracle.py`) scores a family against a one-sentence reading of its contract. This page
records, per family, the contract sentence (`gitgalaxy/standards/signal_contracts.py`), the Python oracle's sentence, and a
verdict: **aligned** (the oracle restates the contract), **realigned** or **added** (this change moved the oracle), or **open
question** (the contract is silent and only the owner can rule; the oracle's reading stands as provisional).

All 12 `draft` contracts are now `declared` (`docs/planted_family_contracts.md`, `docs/resource_family_contracts.md`,
`docs/unplanted_family_contracts.md`); none is left as a question. The five questions #8862 opened are answered by the
contracts (rows below). Scores are from the self-scan DB at this commit (29,706 Python functions; exploratory, not a pinned corpus).

| family | contract status | contract | Python oracle reading | verdict | note |
|---|---|---|---|---|---|
| `branch` | stated | A keyword or operator that opens a runtime choice between control-flow paths: the choosing construct or one of its alternative arms | decision points: if/elif arms, loops, conditional expressions, comprehension filters (not boolean operators: those are short_circuit's, corollary 0; not except handlers, assert, return or break: corollaries 1 and 3) | realigned | Boolean operators dropped from the oracle: they are `short_circuit`'s since #8939 (branch contract corollary 0). On the self-scan DB branch scores 1.00 / 0.80 (over-counts; the engine counts 16,503 functions' worth against the oracle's 13,159: cause not traced). |
| `short_circuit` | declared | A boolean operator whose right operand is evaluated only when the left does not already decide the result: `&&`/`//`, `and`/`or`, `and then`/`or else`, and the shell's `&&`/`//` chaining | boolean operators whose right operand is evaluated only when the left does not decide: and, or | added | New oracle family, `and`/`or` operands. Self-scan DB: 1.00 / 0.96. |
| `args` | stated | The parameters a callable declares | declared parameters | aligned | The oracle sentence restates the contract for Python. |
| `closures` | declared | The syntax that opens an anonymous callable -- a lambda, arrow function, block literal or inline callback -- at the point it is defined | anonymous callables: lambdas (nested named functions are declarations, not closures) | aligned | Lambdas only; a nested def is a declaration (answers #8862 question 3). |
| `comprehensions` | declared | A collection-transform expression -- a comprehension, a map/filter/fold/for-each call, or an inline iteration form -- at its invocation | comprehensions, generator expressions and map/filter/reduce calls | open question | The oracle counts generator expressions; the contract says "a comprehension, a map/filter/fold/for-each call, or an inline iteration form", which neither names nor excludes them. Owner to rule. `lazy_evaluation` excludes them (contract). |
| `decorators` | declared | A metadata attribute attached to the declaration it precedes -- an annotation, attribute, pragma or directive line -- in the language's attribute syntax | decorators on the function itself | aligned | The oracle sentence restates the contract for Python. |
| `io` | stated | An operation that moves data between the program and a system outside its own runtime | opens or reads/writes a file, lists or globs a directory (not path string work, not process exit) | aligned | The oracle sentence restates the contract for Python. |
| `regex_execution` | declared | A site that evaluates a regular expression -- a match, substitution or split operator, a regex constructor or compile/exec call -- at its invocation | evaluates a regular expression: re.* module calls or a match/search/fullmatch/finditer/findall/sub/subn call | aligned | The oracle sentence restates the contract for Python. |
| `time_date_logic` | declared | A site that instantiates or computes with a clock or calendar value -- a now/time/date constructor, duration arithmetic, a formatting or timezone call -- at its invocation | instantiates or computes with a clock or calendar value: now/time/date constructors, durations, formatting and timezone calls | aligned | The oracle sentence restates the contract for Python. |
| `serialization_parsing` | declared | A call that encodes to or decodes from a structured interchange format -- JSON, XML, YAML, CSV, protocol buffers, a marshal or unmarshal -- at its invocation | encodes to or decodes from a structured interchange format: json, yaml, csv, xml, pickle, marshal, protobuf calls | aligned | JSON, YAML, CSV, XML, pickle and marshal (answers #8862 question 1; the rule was fixed by #8882). |
| `high_risk_execution` | stated | A SITE THAT HANDS CONTROL OUT OF THE PROGRAM'S OWN SEMANTICS -- it ends or halts the process, runs text or another program as code, loads or rewrites executable code at run time, destroys a whole store the program does not own, or steps outside the runtime's protections -- in the primitive's own invocation or statement form. | hands control out of the program's semantics: eval, exec, subprocess calls, os.system, process exit | aligned | The oracle sentence restates the contract for Python. |
| `thread_sleeps` | declared | A call that blocks the current thread or schedules a forced delay -- a sleep, a timed wait, a timeout-driven deferral -- at its invocation | blocks the thread or forces a delay: sleep calls | aligned | The oracle sentence restates the contract for Python. |
| `panics_and_aborts` | declared | A statement that ends the current execution context by raising or aborting -- a throw or raise, a panic, an unreachable marker, a fatal-error, revert or process-exit call -- in statement or call form | ends the execution context: raise statements and process-exit calls | open question | `raise` is counted. For other languages the open question is whether `assert` is an abort (C precision 0.48, #8868); the contract does not name it. |
| `debug_prints` | declared | A site that writes text to the console or a diagnostic stream for a developer to read while the program runs -- a print, echo, dump or trace call -- in its own call or statement form; output addressed to a file or writer, and structured logging (telemetry), are not sites | ad-hoc debug output: print calls | aligned | A print call to the console; output addressed to a writer is excluded by the contract (answers the Go `Fprintf` row of #8868). |
| `explicit_casts` | declared | A site that converts a value's type explicitly -- a cast expression, a conversion call or a cast keyword -- in cast form | explicit type conversion: int, str, float, bool, bytes, list, dict, set, tuple calls | aligned | The oracle sentence restates the contract for Python. |
| `bitwise_ops` | declared | A bitwise operator applied between value operands -- shift, and, or, xor, or the unary complement -- in operator position | bitwise operators in operator position: << >> ^ & / ~ | aligned | The oracle sentence restates the contract for Python. |
| `lazy_evaluation` | declared | A deferred-execution construct at its site -- a yield statement, a generator or iterator type annotation, an async-generator form | deferred execution: yield / yield from, or a Generator / Iterator annotation (generator expressions are not listed in the contract) | aligned | yield or a Generator/Iterator annotation; generator expressions are not listed (answers #8862 question 2). |
| `telemetry` | declared | A call that records a log line, a metric or a trace through a logging or observability framework, as opposed to a bare print to standard output -- in the framework's own call form | logger calls | aligned | Logger calls; the #9207 contract fixes telemetry as framework logging, metrics and traces (answers #8862 question 5). Python over-counts (precision 0.22 on the self-scan DB): an engine gap, not a reading. |
| `concurrency` | declared | A site that starts, schedules, awaits or hands off work to run concurrently with its caller -- an async or await keyword, a task, thread, goroutine or promise constructor, an executor or timer submission -- in its own keyword or call form | threads, pools, processes, queues, executor submits | aligned | The oracle sentence restates the contract for Python. |
| `sync_locks` | declared | A site that acquires, releases or wraps a mutual-exclusion or atomic-ordering primitive so that threaded code does not race -- a lock or unlock call, a mutex, semaphore or synchronized region, an atomic operation -- in its own invocation form | locks, semaphores, acquire and release | aligned | The oracle sentence restates the contract for Python. |
| `globals` | stated | A declaration of a binding with program lifetime -- file, module, class-static or process scope -- or a read or write of the process's ambient environment through its named handle | global / nonlocal statements and reads of os.environ, sys.argv, sys.path | aligned | The oracle sentence restates the contract for Python. |
| `import` | stated | A statement or directive that binds an external unit -- a module, package, header, library, file, stage or base image -- into the current unit, in the language's own dependency form | import statements inside the function | aligned | The oracle sentence restates the contract for Python. |
| `cleanup` | stated | A SITE THAT EXPLICITLY DESTROYS STATE OR RELEASES A HELD RESOURCE -- a deallocation or finalization call, a handle or connection close, removal of an entry from a live container or of external state the program owns, or the opener of a guaranteed-teardown region -- in call or statement form. | destroys state or releases a held resource: with blocks, try/finally, close/remove/unlink/rmtree calls, del | aligned | with, try/finally, del and close/remove calls match the contract wording; Python recall is low (0.15 on the self-scan DB): an engine gap (answers #8862 question 4). |
| `doc` | declared | A comment block in the language's structured documentation form -- the form a documentation tool or IDE parses, such as a doc comment, a docstring or a tagged block -- read from the comment surface | has a docstring (structured documentation) | open question | Python docstrings count. Which structured form counts in a language without `/** */` is an owner question (#8868). |

## Non-Python oracles (tree-sitter)

`family_oracle_ts.py` holds one sentence per family for every language it scores (Go, Java, JavaScript, TypeScript, Rust, C, C++ and
the per-language specs in `family_oracle_specs_a.py` / `family_oracle_specs_b.py`: C#, Kotlin, Swift, Scala, Ruby, PHP, Lua, shell).
A language whose spec lists a family in `skip_families` has no oracle for it. Since #9256 these oracles count boolean operators under
`short_circuit`, not `branch`, as the branch contract's corollary 0 says.

| family | tree-sitter oracle reading | verdict | note |
|---|---|---|---|
| `branch` | decision points: if/else arms, loops, case/default arms, conditional expressions (not && and //: those are short_circuit's, corollary 0; not catch handlers, goto, return or break: contract corollaries 1 and 3) | realigned | Boolean operators moved to `short_circuit` (branch corollary 0, #8939) by the slice-1 change (#9256). Cells in `tests/family_validity_baseline.json` predate it (see below). |
| `short_circuit` | boolean operators whose right operand is evaluated only when the left does not decide: && // and or | added | New tree-sitter family, as the Python oracle's since #9252: `&&`, `||`, `and`, `or`. |
| `args` | declared parameters | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `closures` | anonymous callables: function literals, lambdas, arrow functions, closures | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `decorators` | annotations, attributes or decorators on the function | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `panics_and_aborts` | throw / panic / unreachable marker / process exit | open question | Whether `assert` is an abort is an owner question (#8868, C precision 0.48). |
| `bitwise_ops` | bitwise operators in operator position: << >> ^ & / ~ (and the compound assignments) | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `debug_prints` | ad-hoc debug output to the console | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `thread_sleeps` | sleeps and timed waits | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `regex_execution` | evaluates or builds a regular expression | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `time_date_logic` | instantiates or computes with a clock or calendar value: now/time/date constructors, durations, formatting | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `io` | opens or reads/writes a file or a network connection | provisional | Not re-read for the contracts in this change; the sentence is the tree-sitter oracle's working reading. |
| `doc` | structured documentation directly above (/** */, ///, godoc) | open question | Which structured form counts in a language without `/** */` is an owner question (#8868). |

Per-language readings that differ from the shared sentence:

| language | reading | verdict |
|---|---|---|
| C#, PHP | `??` and `??=` stay under `branch` (value-selection operators; the short_circuit contract does not name them) | open question (owner) |
| Ruby | `\|\|=` and `&&=` count under `short_circuit`; `rescue` / `ensure` are handlers, not branches (corollary 1) | aligned |
| Kotlin, Swift | conjunction and disjunction nodes count under `short_circuit` | aligned |
| Scala | a `case` clause under a `catch` is a handler, not a decision (corollary 1) | aligned |
| shell | `&&` / `\|\|` list chaining counts under `short_circuit` | aligned |

The non-Python `branch` cells in `tests/family_validity_baseline.json` were measured before this realignment and there is no
`short_circuit` cell yet: they are rescanned per corpus (`family_oracle.py --lang X --corpus NAME --update-baseline`), not here.

## Open owner questions

1. Is `assert` an abort for `panics_and_aborts`? (#8868, C precision 0.48.)
2. Which documentation form counts for `doc` in a language without `/** */`? (#8868.)
3. Does `comprehensions` include generator expressions?
4. `llm_api` has a rule only for python, javascript and typescript; an absence entry is owed per language with an SDK (`docs/unplanted_family_contracts.md`).
5. Is `??` (and `??=`) a `short_circuit` operator in C# and PHP? Until ruled it counts under `branch`.
