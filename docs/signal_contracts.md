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
3. The recorded count of a few signals is not the raw hit count: `core/spatial_correlation.py`
   adds proximity adjustments in place (the x3 cascading flux on `state_mutation`, the
   silencer dampener on `high_risk_execution`, the race and exfiltration amplifiers; see
   `core/README.md`'s proximity table, gitgalaxy#2546/#2631). The raw count is recoverable
   from `mitigation_telemetry`. docs/contract_roadmap.md Phase 2 moves these adjustments
   out of the recorded count so that a count is a count.

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

2 stated, 66 draft. A **draft** row is the schema comment transcribed as-is; a **stated** row has been audited across the corpus languages and has a contract doc. `planted` = the keyword-rosetta corpus plants a known count of it (so the cross-language gate can hold it equal); unplanted signals that feed a risk formula are the ones the roadmap's Phase 3 must plant or declare absent.

| signal | phase | kind | status | planted | contract | doc |
|---|---|---|---|---|---|---|
| `args` | structure | `declaration` | stated | yes | The parameters a callable declares | [args_rule_contract.md](../docs/args_rule_contract.md) #2773 |
| `branch` | structure | `site` | draft | yes | Control flow that forces the CPU to make a decision or jump |  |
| `class_start` | structure | `declaration` | draft | yes | The syntax that defines an object-oriented class, struct, or record |  |
| `func_start` | structure | `declaration` | draft | yes | Exact syntax anchoring the start of an executable block of logic |  |
| `structural_boundaries` | structure | `tally` | draft |  | Keywords defining structural boundaries and straight-line execution |  |
| `api` | safety | `declaration` | stated |  | A declaration that makes a named function or type visible outside this file | [api_rule_contract.md](../docs/api_rule_contract.md) #2730 |
| `dead_code` | safety | `annotation` | draft |  | Commented-out structural code and unused logic trails |  |
| `doc` | safety | `annotation` | draft | yes | Structured documentation meant to be parsed by IDEs or generators |  |
| `high_risk_execution` | safety | `site` | draft | yes | Process-killing commands and catastrophic runtime vulnerabilities |  |
| `io` | safety | `site` | draft | yes | Interaction with the disk, network, or external systems |  |
| `safety` | safety | `site` | draft | yes | Defensive programming constructs that prevent crashes at runtime |  |
| `safety_bypasses` | safety | `site` | draft | yes | Syntax that actively bypasses type safety, swallows errors, or relies on unpredictable state |  |
| `state_mutation` | safety | `site` | draft | yes | Reassignment of variables or modifying collections | #2765 |
| `test` | safety | `site` | draft | yes | Assertions and unit testing framework keywords |  |
| `closures` | architecture | `declaration` | draft |  | Anonymous functions, lambdas, inline callbacks |  |
| `comprehensions` | architecture | `site` | draft |  | Collection iterators or inline looping |  |
| `concurrency` | architecture | `site` | draft |  | Asynchronous logic and parallel execution |  |
| `decorators` | architecture | `annotation` | draft |  | Annotations applied to classes/methods |  |
| `generics` | architecture | `annotation` | draft |  | Type parameters indicating generic abstractions |  |
| `globals` | architecture | `declaration` | draft | yes | Accessing global state, environment variables, or system registries |  |
| `import` | architecture | `declaration` | draft | yes | Dependency resolution and module loading |  |
| `ownership` | architecture | `annotation` | draft | yes | Authorship metadata |  |
| `reflection_metaprogramming` | architecture | `site` | draft |  | Metaprogramming, reflection, and dynamic property assignment |  |
| `scientific` | architecture | `site` | draft |  | Math, data science, and complex rendering libraries |  |
| `ui_framework` | architecture | `site` | draft |  | DOM manipulation, UI components |  |
| `dependency_injection` | subsystems | `annotation` | draft |  | Inversion of Control (IoC) injection markers |  |
| `events` | subsystems | `site` | draft |  | Event-driven architecture signatures and message brokers |  |
| `fragile_debt` | subsystems | `annotation` | draft | yes | Explicit admissions of fragile or dangerous logic |  |
| `hardcoded_secrets` | subsystems | `site` | draft |  | Static credentials or API keys baked into code |  |
| `inline_asm` | subsystems | `site` | draft |  | Direct CPU architecture bridging |  |
| `macros` | subsystems | `declaration` | draft |  | Compiler pragmas or macro definitions that generate code at compile-time |  |
| `memory_alloc` | subsystems | `site` | draft |  | Explicit unmanaged memory allocations and raw heap manipulations |  |
| `planned_debt` | subsystems | `annotation` | draft | yes | Annotated future work |  |
| `pointers` | subsystems | `site` | draft |  | Explicit tracking of raw memory addressing and pointer dereferencing |  |
| `spec_exposure` | subsystems | `annotation` | draft |  | Audit tags establishing traceability of intent |  |
| `ssr_boundaries` | subsystems | `site` | draft |  | Server-Side Rendering computation boundaries |  |
| `bitwise_ops` | resources | `site` | draft |  | Bitwise operations manipulating raw bytes |  |
| `cleanup` | resources | `site` | draft | yes | Explicitly destroying state or releasing resources |  |
| `debug_prints` | resources | `site` | draft |  | Ad-hoc, temporary debug statements |  |
| `encapsulation` | resources | `annotation` | draft |  | Explicitly hiding logic from the rest of the application | #2766 |
| `explicit_casts` | resources | `site` | draft |  | Explicitly bypassing the compiler's type-checker |  |
| `immutability_locks` | resources | `annotation` | draft |  | Explicitly locking data so it cannot be mutated | #2772 |
| `listeners` | resources | `site` | draft |  | Waiting to receive state from an external broadcast |  |
| `panics_and_aborts` | resources | `site` | draft |  | Forcefully destroying the current execution context |  |
| `sync_locks` | resources | `site` | draft |  | Explicitly coordinating threaded logic to prevent race conditions |  |
| `telemetry` | resources | `site` | draft | yes | Structured logging and observability frameworks |  |
| `test_skip` | resources | `annotation` | draft |  | Bypassed tests or ignored verification specs |  |
| `thread_sleeps` | resources | `site` | draft |  | Thread blocking or forced timeouts |  |
| `ipc_rpc_bridges` | hybrid | `site` | draft |  | Inter-process or RPC bridging commands |  |
| `regex_execution` | hybrid | `site` | draft |  | Native regex evaluation commands |  |
| `serialization_parsing` | hybrid | `site` | draft |  | JSON, XML, YAML parsing libraries |  |
| `time_date_logic` | hybrid | `site` | draft |  | Time/date instantiation and math |  |
| `cryptography` | ai-ml | `site` | draft |  | Cryptographic primitives and identity libraries |  |
| `dl_frameworks` | ai-ml | `site` | draft |  | Deep learning frameworks |  |
| `hardware_bridge` | ai-ml | `site` | draft |  | Bridges from software into physical/peripheral I/O |  |
| `lazy_evaluation` | ai-ml | `site` | draft |  | Generators and deferred-execution constructs |  |
| `llm_api` | ai-ml | `site` | draft |  | Direct calls into a hosted LLM provider SDK |  |
| `llm_orchestrator` | ai-ml | `site` | draft |  | Agent/RAG orchestration frameworks |  |
| `llm_vector_store` | ai-ml | `site` | draft |  | Vector database clients |  |
| `ml_traditional` | ai-ml | `site` | draft |  | Classical (non-deep-learning) ML libraries |  |
| `vectorized_math` | ai-ml | `site` | draft |  | Tensor/matrix math operations |  |
| `exfiltration_camouflage` | appsec | `site` | draft |  | Outbound HTTP calls disguised as telemetry/metrics/audit traffic |  |
| `memory_scraping` | appsec | `site` | draft |  | Direct reads of process memory |  |
| `rce_funnel` | appsec | `site` | draft |  | Spawning a shell/interpreter subprocess from application code |  |
| `lit_code_blocks` | literate | `site` | draft |  | Fenced code block delimiters |  |
| `lit_diagrams` | literate | `site` | draft |  | Embedded diagram blocks |  |
| `lit_headers` | literate | `declaration` | draft |  | Section headers, for document structure/navigation mapping |  |
| `lit_links` | literate | `site` | draft |  | Links to other documents or resources, captured as document dependencies |  |

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
