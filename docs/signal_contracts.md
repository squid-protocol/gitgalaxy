# Signal contracts

> Rendered from `gitgalaxy/standards/signal_contracts.py` by `tests/signal_contract_audit.py --render`.
> Do not edit by hand -- edit the module and re-render. Roadmap and rationale:
> `docs/contract_roadmap.md`; the method for taking a row from *draft* to *stated*:
> `.claude/skills/rule-contract-audit/SKILL.md`.

## The stream contract

**A rule runs over the file's code stream: the text left after `prism.py` removes the
comment surface for the language's `lexical_family`. String literals are never masked,
for any rule, in any language** (gitgalaxy#2535 traced this to ground with direct scans:
there is no shielding mechanism). Corollaries:

1. A keyword inside a string literal is a real hit for every rule. A rule that must not
   count one has to exclude it itself; a corpus that plants a decoy inside a string is
   testing the rule, not the stream (keyword-rosetta #17, #71, #73).
2. Comment-stream rules (`dead_code`, `doc`, `ownership`, `planned_debt`, `fragile_debt`,
   `spec_exposure`) read the comment surface instead; a language whose comment syntax
   `prism.py` does not know sends its comments into the code stream (gitgalaxy#2610, jcl).
   The literate pack (`lit_code_blocks`, `lit_diagrams`, `lit_headers`, `lit_links`) is the
   same shape for markdown: `prism.py`'s Prose Bypass routes the whole file into the comment
   stream and `detector.comment_analysis` runs the four rules there (#691) -- probed on the
   code stream they read 0 on every file.
3. The recorded count is the raw hit count, for every signal (gitgalaxy#2813). The
   proximity pairs in `core/spatial_correlation.py` (the x3 cascading flux on
   `state_mutation`, the silencer dampener on `high_risk_execution`, the race and
   exfiltration amplifiers; see `core/README.md`'s proximity table) tally into the per-file
   `mitigation_telemetry` and are applied only in the score layer's weighted view
   (`weighted_count()`); a corpus, recorder or manifest never sees them in a count.
4. For the C family (`c`, `cpp`, `objective-c`, `cs`, `swift`), a statically-dead
   preprocessor branch is NOT in the code stream a rule counts (gitgalaxy#2814):
   `detector._blank_dead_preproc_branches` blanks the body of `#if 0` and the dead side of
   `#if 1` before the rule loop, mirroring the `#1720` macro shield that already prunes those
   branches for function-boundary detection. An unknown condition (`#if FOO`, `#ifdef X`,
   `#if defined(X)`) keeps BOTH branches -- their hits are counted as live, since the engine
   cannot decide the condition without a macro table. The branch's own
   `#if/#elif/#else/#endif` markers and every live directive stay in the stream, so rules
   that match directives (cpp `import` on `#include`, csharp `safety_bypasses` on
   `#pragma warning disable`, objective-c `import` on `#import`) are unaffected.

## The count contract (what every row below promises)

**One hit is one instance of the construct the signal's sentence names, in this file, as
written.** Corollaries every audited contract has needed so far:

1. **A reference is not a declaration.** A call site, an import, a type annotation naming
   the construct, a `switch` case on the keyword -- these consume a name; they do not
   declare, annotate or mutate anything (api corollary 1; haskell `IORef` in a type
   signature, gitgalaxy#2765).
2. **A modifier counts where it modifies, not wherever it appears.** `\bpublic\b` or
   `\bstatic\b` against the code stream counts the word. The rule must anchor the
   modifier to the declaration it applies to (api corollary 2).
3. **Where the language makes the property the default, say which side counts.** Either
   the declaration itself is the marker (api corollary 3: public-by-default languages count
   `def`), or the language records a contract-level absence (`None` rule + a ledgered
   `intended-morphology` entry) rather than a manufactured construct. The two answers cannot
   coexist inside one signal (gitgalaxy#2772: swift `let` is an annotation chosen against
   `var`; rust `let` is not an annotation at all).
4. **A token already owned by another rule for the same construct is not a second signal**
   (dockerfile `ENV` is `globals`, not also `state_mutation`; keyword-rosetta's
   `keyword-overlap` disposition records the exceptions that are deliberate).
5. **The count's unit is fixed by its kind** (table below) and a formula may only add,
   subtract or compare counts of the same unit. That is the check Phase 4 automates.

## Kinds and units

| kind | one hit is | unit |
|---|---|---|
| `declaration` | a thing declared: a function, class, parameter list, global, import, macro | `declarations` |
| `site` | a code site where the construct is used or invoked: a decision, a write, a call, an allocation | `sites` |
| `annotation` | a marker attached to a declaration, statement or comment: a modifier, a tag, a doc block | `annotations` |
| `tally` | a vocabulary token with no structural referent; a length-like quantity, never a denominator | `tokens` |

## Signals

16 stated, 40 declared, 12 draft. A **draft** row is the schema comment transcribed as-is; a **declared** row has a fixed language-independent sentence, kind and unit, measured incidence and its disagreeing rules filed but not edited (#2897, `docs/domain_sensor_contracts.md`); a **stated** row has been audited across the corpus languages, its rules edited to agree, and has a contract doc. `planted` = the keyword-rosetta corpus plants a known count of it (so the cross-language gate can hold it equal); unplanted signals that feed a risk formula are the ones the roadmap's Phase 3 must plant or declare absent.

| signal | phase | kind | status | planted | contract | doc |
|---|---|---|---|---|---|---|
| `args` | structure | `declaration` | stated | yes | The parameters a callable declares | [args_rule_contract.md](../docs/args_rule_contract.md) #2773 |
| `branch` | structure | `site` | stated | yes | A keyword or operator that opens a runtime choice between control-flow paths: the choosing construct or one of its alternative arms | [branch_rule_contract.md](../docs/branch_rule_contract.md) #2822 |
| `class_start` | structure | `declaration` | stated | yes | The declaration of a named type -- a class, struct, record, interface, enum or object -- or the file's compilation-unit container where that container is the language's only named-entity declaration | [class_start_rule_contract.md](../docs/class_start_rule_contract.md) #2856 |
| `func_start` | structure | `declaration` | stated | yes | The syntax that opens an executable block of logic under its own name: a function, method, procedure or subroutine declaration, or the instruction that begins an executable step in a language with no named-callable form | [func_start_rule_contract.md](../docs/func_start_rule_contract.md) #2856 |
| `structural_boundaries` | structure | `tally` | declared |  | A vocabulary token of straight-line execution or structural delimiting -- a return, a declaration or import keyword, a type keyword, an instruction mnemonic in a language with no other structure -- counted as a length-like tally with no structural referent | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `api` | safety | `declaration` | stated |  | A declaration that makes a named function or type visible outside this file | [api_rule_contract.md](../docs/api_rule_contract.md) #2730 |
| `dead_code` | safety | `annotation` | draft |  | Commented-out structural code and unused logic trails |  |
| `doc` | safety | `annotation` | draft | yes | Structured documentation meant to be parsed by IDEs or generators |  |
| `high_risk_execution` | safety | `site` | stated | yes | A SITE THAT HANDS CONTROL OUT OF THE PROGRAM'S OWN SEMANTICS -- it ends or halts the process, runs text or another program as code, loads or rewrites executable code at run time, destroys a whole store the program does not own, or steps outside the runtime's protections -- in the primitive's own invocation or statement form. | [high_risk_execution_rule_contract.md](../docs/high_risk_execution_rule_contract.md) #2878 |
| `io` | safety | `site` | stated | yes | An operation that moves data between the program and a system outside its own runtime | [io_rule_contract.md](../docs/io_rule_contract.md) #2841 |
| `safety` | safety | `site` | stated | yes | A site that handles or forestalls a runtime failure at the value level -- a guarded region's opener or its typed handler, a runtime assertion or validation call, a fallback or handled-absence form, an installed failure handler or watchdog, or a hardening instruction -- in a form an ordinary identifier, type annotation or constructor cannot match | [safety_rule_contract.md](../docs/safety_rule_contract.md) #2869 |
| `safety_bypasses` | safety | `site` | draft | yes | Syntax that actively bypasses type safety, swallows errors, or relies on unpredictable state |  |
| `state_mutation` | safety | `site` | stated | yes | A statement that writes a new value into state that already exists | [state_mutation_rule_contract.md](../docs/state_mutation_rule_contract.md) #2765 |
| `test` | safety | `site` | stated | yes | A site that engages a testing framework: a test-case or fixture declaration, a framework assertion or expectation, or the framework named as such | [test_rule_contract.md](../docs/test_rule_contract.md) #2852 |
| `closures` | architecture | `declaration` | declared |  | The syntax that opens an anonymous callable -- a lambda, arrow function, block literal or inline callback -- at the point it is defined | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `comprehensions` | architecture | `site` | declared |  | A collection-transform expression -- a comprehension, a map/filter/fold/for-each call, or an inline iteration form -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `concurrency` | architecture | `site` | draft |  | Asynchronous logic and parallel execution |  |
| `decorators` | architecture | `annotation` | declared |  | A metadata attribute attached to the declaration it precedes -- an annotation, attribute, pragma or directive line -- in the language's attribute syntax | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `generics` | architecture | `annotation` | declared |  | A type-parameter list on a declaration or an instantiation -- the bracketed parameters that make a type or callable generic -- in the language's parameterisation syntax | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `globals` | architecture | `declaration` | stated | yes | A declaration of a binding with program lifetime -- file, module, class-static or process scope -- or a read or write of the process's ambient environment through its named handle | [globals_rule_contract.md](../docs/globals_rule_contract.md) #2858 |
| `import` | architecture | `declaration` | stated | yes | A statement or directive that binds an external unit -- a module, package, header, library, file, stage or base image -- into the current unit, in the language's own dependency form | [import_rule_contract.md](../docs/import_rule_contract.md) #2875 |
| `ownership` | architecture | `annotation` | stated | yes | A tag naming who is responsible for the unit -- an author, creator, maintainer, owner, developer or contact -- with its value, in the form the language's tooling or header convention reads as metadata | [ownership_rule_contract.md](../docs/ownership_rule_contract.md) #2882 |
| `reflection_metaprogramming` | architecture | `site` | draft |  | Metaprogramming, reflection, and dynamic property assignment |  |
| `scientific` | architecture | `site` | declared |  | A call into, or an import of, a numeric, scientific or rendering library facility -- a math function, a linear-algebra or matrix type, an array, plotting or GPU library -- in its qualified, typed or call form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `ui_framework` | architecture | `site` | declared |  | A call, declaration or markup construct that builds or mutates a user-interface surface through a UI framework or the document tree -- a component or widget definition, a hook or lifecycle call, a DOM query or mutation, a layout or rendering directive -- in the framework's own invocation or property form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `dependency_injection` | subsystems | `annotation` | declared |  | An inversion-of-control marker -- an injection annotation, a provider or module registration, a container or factory declaration -- attached to the declaration it wires | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `events` | subsystems | `site` | declared |  | A site that publishes into or wires up an event or message channel -- an emit or dispatch call, a broker or bus client construction, a signal connect -- in call form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `fragile_debt` | subsystems | `annotation` | draft | yes | Explicit admissions of fragile or dangerous logic |  |
| `hardcoded_secrets` | subsystems | `site` | declared |  | A literal credential written into the file -- a password, token, key or secret assigned or configured as a string literal of credential length -- at the assignment | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `inline_asm` | subsystems | `site` | declared |  | The opener of an embedded machine-code region -- an inline-assembly statement, block or intrinsic -- in the language's embedding syntax | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `macros` | subsystems | `declaration` | declared |  | A compile-time code-generation directive -- a macro definition, a conditional-compilation or include directive, a compiler pragma -- in directive form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `memory_alloc` | subsystems | `site` | declared |  | A call that requests memory from the runtime or the heap explicitly -- an allocator call, an explicit object or buffer construction, a manual resize -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `planned_debt` | subsystems | `annotation` | draft | yes | Annotated future work |  |
| `pointers` | subsystems | `site` | declared |  | A site that takes, holds or dereferences a raw memory address -- an address-of, a pointer declaration or dereference, an unsafe pointer or raw-handle type -- in the language's pointer syntax | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `spec_exposure` | subsystems | `annotation` | draft |  | Audit tags establishing traceability of intent |  |
| `ssr_boundaries` | subsystems | `site` | declared |  | A server-side rendering boundary -- a framework's data-loading or render-mode hook, a server/client directive, or a template-render call -- in the framework's own form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `bitwise_ops` | resources | `site` | declared |  | A bitwise operator applied between value operands -- shift, and, or, xor, or the unary complement -- in operator position | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `cleanup` | resources | `site` | stated | yes | A SITE THAT EXPLICITLY DESTROYS STATE OR RELEASES A HELD RESOURCE -- a deallocation or finalization call, a handle or connection close, removal of an entry from a live container or of external state the program owns, or the opener of a guaranteed-teardown region -- in call or statement form. | [cleanup_rule_contract.md](../docs/cleanup_rule_contract.md) #2888 |
| `debug_prints` | resources | `site` | draft |  | Ad-hoc, temporary debug statements |  |
| `encapsulation` | resources | `annotation` | stated |  | One hit is a declaration-position marker that excludes a name from the public surface, in the language's own morphology | [encapsulation_rule_contract.md](../docs/encapsulation_rule_contract.md) #2766 |
| `explicit_casts` | resources | `site` | declared |  | A site that converts a value's type explicitly -- a cast expression, a conversion call or a cast keyword -- in cast form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `immutability_locks` | resources | `annotation` | stated |  | AN ADDED MARKER OR LOCK CALL THAT PREVENTS A BINDING OR VALUE FROM BEING CHANGED AFTER INITIALISATION, WHERE THE LANGUAGE'S DEFAULT WOULD PERMIT IT -- a modifier or qualifier on an otherwise-mutable declaration, a restricted constant-declaration form distinct from the general-purpose binding, a runtime lock call, or an immutable reference pin; the language's ordinary binding keyword is a binding choice, not a lock, and a language whose bindings are immutable by default records the stated absence. | [immutability_locks_rule_contract.md](../docs/immutability_locks_rule_contract.md) #2772 |
| `listeners` | resources | `site` | declared |  | A registration to receive from an external broadcast -- an event-listener, subscription or handler-binding call -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `panics_and_aborts` | resources | `site` | declared |  | A statement that ends the current execution context by raising or aborting -- a throw or raise, a panic, an unreachable marker, a fatal-error, revert or process-exit call -- in statement or call form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `sync_locks` | resources | `site` | draft |  | Explicitly coordinating threaded logic to prevent race conditions |  |
| `telemetry` | resources | `site` | draft | yes | Structured logging and observability frameworks |  |
| `test_skip` | resources | `annotation` | declared |  | A marker that disables or ignores a test -- a skip decorator, an ignore attribute, a `.skip`/`xit` call form -- attached to the test it silences | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `thread_sleeps` | resources | `site` | declared |  | A call that blocks the current thread or schedules a forced delay -- a sleep, a timed wait, a timeout-driven deferral -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `ipc_rpc_bridges` | hybrid | `site` | declared |  | A site that crosses a process or host boundary through a bridge -- an RPC or IPC client or server construction, a pipe or socket-message send, a foreign-function or platform-channel call -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `regex_execution` | hybrid | `site` | declared |  | A site that evaluates a regular expression -- a match, substitution or split operator, a regex constructor or compile/exec call -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `serialization_parsing` | hybrid | `site` | declared |  | A call that encodes to or decodes from a structured interchange format -- JSON, XML, YAML, CSV, protocol buffers, a marshal or unmarshal -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `time_date_logic` | hybrid | `site` | declared |  | A site that instantiates or computes with a clock or calendar value -- a now/time/date constructor, duration arithmetic, a formatting or timezone call -- at its invocation | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `cryptography` | ai-ml | `declaration` | declared |  | An import of a cryptographic-primitive, hashing, transport-security or identity library from the pack's name list -- one hit per import statement | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `dl_frameworks` | ai-ml | `declaration` | declared |  | An import of a deep-learning framework from the pack's name list -- one hit per import statement, none for a use of the imported name | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `hardware_bridge` | ai-ml | `declaration` | declared |  | An import of a library that bridges software into physical or peripheral I/O -- serial, USB, bluetooth, printers, device sockets -- one hit per import statement | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `lazy_evaluation` | ai-ml | `site` | declared |  | A deferred-execution construct at its site -- a yield statement, a generator or iterator type annotation, an async-generator form | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `llm_api` | ai-ml | `site` | draft |  | Direct calls into a hosted LLM provider SDK |  |
| `llm_orchestrator` | ai-ml | `declaration` | declared |  | An import of an agent or retrieval-orchestration framework from the pack's name list -- one hit per import statement, none for a use of the imported name | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `llm_vector_store` | ai-ml | `declaration` | declared |  | An import of a vector-database client from the pack's name list -- one hit per import statement, none for a use of the imported name | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `ml_traditional` | ai-ml | `declaration` | declared |  | An import of a classical (non-deep-learning) machine-learning library from the pack's name list -- one hit per import statement, none for a use of the imported name | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `vectorized_math` | ai-ml | `site` | declared |  | A tensor or matrix operation at its site -- an einsum/matmul/tensordot/dot call, or the infix matrix-multiply operator between two value operands | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `exfiltration_camouflage` | appsec | `site` | declared |  | An outbound HTTP call whose target or payload carries a telemetry-, metrics-, audit- or log-shaped name -- at the call | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `memory_scraping` | appsec | `site` | declared |  | A read of another process's memory image through the operating system's process filesystem -- at the path construction or open | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `rce_funnel` | appsec | `site` | declared |  | A subprocess spawn from application code whose command is a shell or interpreter -- at the spawn call, with the interpreter name in the command | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `lit_code_blocks` | literate | `site` | declared |  | A fence line that opens or closes a code block -- a block contributes its opener and its closer, so one block is two hits | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `lit_diagrams` | literate | `site` | declared |  | A fence line that opens an embedded diagram block by its info string -- one hit per diagram | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `lit_headers` | literate | `declaration` | declared |  | An ATX heading line -- one to six `#` at the margin followed by a space -- one hit per heading | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |
| `lit_links` | literate | `site` | declared |  | An inline link or image target `[text](target)` -- one hit per link | [domain_sensor_contracts.md](../docs/domain_sensor_contracts.md) #2897 |

## Score contracts (the formulas over these units)

1 stated, 0 draft -- contract roadmap Phase 4 (#2812). A **stated** score contract pins what the 0-100 number MEANS as one language-independent sentence over the units above; its equation, decisions and acceptance table live in the doc, and `tests/tools/audit_score_inputs.py <metric>` keeps it honest (every recorded score reproduced from its recorded inputs). The method is the `score-contract-audit` skill; #2908 is the worked precedent the remaining formulas copy.

| score | status | contract | doc |
|---|---|---|---|
| `risk_documentation` | stated | Of the units extracted from a file (functions, methods, paragraphs, steps), the weight-share a reader cannot recover from documentation: a public unit counts double, a unit's own reflection hits raise its weight, and a folder-level documentation umbrella shields the whole file multiplicatively. A ratio over units, never a density over lines; a file with no extracted units has no value (n/a), not zero | [risk_documentation_contract.md](../docs/risk_documentation_contract.md) #2908 |

## Helper keys (not signals)

| key | purpose |
|---|---|
| `_args_arrow_count_groups` | args strategy: arrow-function parameter groups |
| `_args_bare_body_groups` | args strategy: bare-body parameter groups |
| `_args_colon_selector_groups` | args strategy: colon-selector parameter groups (objective-c) |
| `_args_findall_max_groups` | args strategy: take the maximum over findall groups |
| `_args_findall_sum_groups` | args strategy: sum over findall groups |
| `_args_pattern_list_groups` | args strategy: pattern-list parameter groups |
| `_args_prototype_groups` | args strategy: prototype parameter groups |
| `_args_tcl_pattern_list_groups` | args strategy: tcl pattern-list parameter groups |
| `_dependency_capture` | capture group 1 = the exact dependency path string, for the import DAG |
| `_named_token_capture` | capture group(s) = the exact imported symbol names (AI/ML pack) |
| `_scope_filters` | {rule: filter_name} -- a structural filter detector.py applies after the regex (CRITICAL ENGINE RULE 17) |
| `_visibility_export` | per-function export-statement form, for the api orphan census (#2727/#2729) |
| `_visibility_export_list` | capture group(s) = a region holding MANY exported names, same census (#2823) |
