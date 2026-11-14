# Signals: what each one counts

The engine records about 100 keyword signals per file and per function (`file_data` / `function_data` columns).
Several persisted column names describe something other than what their rules count: `struct_linear` counts structural
keywords (`return`, `def`, `void`, `export`), not "linear code". This page is the reader-facing name for each signal
([gitgalaxy#8009](https://github.com/squid-protocol/gitgalaxy/issues/8009)). Names come from `SIGNAL_DISPLAY_NAMES`
in `gitgalaxy/standards/analysis_lens.py`; `signal_display_name()` accepts a rule key or a column.

Stored column names and JSON keys are unchanged; the audit report's `FRIENDLY_MAP` labels for these signals use the display names (#8009 slice 2b) (display layer only, as with
[`vectors.md`](vectors.md)). Renaming columns waits for an archetype retrain, because archetype features are
densities of these columns.

**How to read the table**
- *function* / *file*: share of rows with a nonzero count in the v2.12.0 population DB (8,173,786 functions and
  1,451,358 files from 745 scanned targets, engine `b64f42bf`). A `0` in *function* with a nonzero *file* means the
  rule only runs file-wide (see [#8012](https://github.com/squid-protocol/gitgalaxy/issues/8012)).
- *typical matches*: the most frequent strings each language's rule matched on the comment-free code stream of
  language-crucible files (lowercased), measured with engine `b64f42bf`, before the #8010 / #8011 fixes. For example,
  C `size_t` no longer counts as `safety`. Known leaks are tracked in
  [#8010](https://github.com/squid-protocol/gitgalaxy/issues/8010) (one token counted by two rules) and
  [#8011](https://github.com/squid-protocol/gitgalaxy/issues/8011). Per-pair dispositions: [`rule_overlap_dispositions.md`](rule_overlap_dispositions.md).

| column | rule key | display name | function | file | typical matches |
|---|---|---|---:|---:|---|
| `struct_branch` | `branch` | Branches & Conditionals | 40.6% | 42.9% | `if`, `else`, `for`, `case`, `&&`, `?` |
| `struct_linear` | `structural_boundaries` | Structural Keywords (return/def/void/export) | 85.3% | 71.7% | `return`, `void`, `auto`, `def`, `=>`, `let` |
| `struct_args` | `args` | Calls & Signatures With Arguments | 89.0% | 59.3% | `def __init__(self)`, `def _get_value(self)`, `() =>`, `function ()`, `function()`, `::` |
| `struct_func_start` | `func_start` | Function Declarations | 98.4% | 54.9% | `def __init__(`, `def update(`, `constructor`, `dispose`, `getmaterialtype`, `fn deserialize<d>` |
| `struct_class_start` | `class_start` | Class / Struct Declarations | 8.3% | 39.9% | `struct cb_field`, `struct symbol`, `class logfallback`, `type buildargs struct`, `struct outer`, `enum field` |
| `struct_closures` | `closures` | Closures & Lambdas | 12.1% | 18.7% | `[&]() {`, `[] {`, `lambda`, `=> {`, `() =>`, `->` |
| `struct_decorators` | `decorators` | Decorators, Annotations & Attributes | 11.6% | 20.4% | `[[fallthrough]]`, `[[maybe_unused]]`, `@classmethod`, `@provide_bucket_name`, `@appname`, `@name` |
| `struct_generics` | `generics` | Generics & Type Parameters | 13.8% | 18.0% | `template <typename t>`, `requires`, `->`, `dict[str, any]`, `<f>`, `<t>` |
| `struct_comprehensions` | `comprehensions` | Comprehensions & Collection Pipelines | 3.1% | 7.7% | `.map(`, `.filter(`, `.foreach(`, `.stream(`, `.collect(`, `array_map` |
| `struct_macros` | `macros` | Preprocessor Directives & Macros | 1.7% | 14.5% | `#endif`, `#define`, `macro_rules!`, `proc_macro_derive`, `macroable` |
| `struct_var_decl` | `core_var_decl` | Variable Declarations | 0 | 52.9% |  |
| `struct_tabs` | `indent_tabs` | Tab Indentation | 0 | 16.8% |  |
| `struct_spaces` | `indent_spaces` | Space Indentation | 0 | 61.7% |  |
| `struct_camel_case` | `design_camel_case` | camelCase Names | 0 | 15.8% |  |
| `struct_snake_case` | `design_snake_case` | snake_case Names | 0 | 43.8% |  |
| `struct_pascal_case` | `design_pascal_case` | PascalCase Names | 0 | 11.5% |  |
| `struct_upper_case` | `design_upper_case` | UPPER_CASE Names | 0 | 9.7% |  |
| `struct_short_vars` | `design_short_vars` | Short Names | 0 | 20.1% |  |
| `struct_long_vars` | `design_long_vars` | Long Names | 0 | 5.8% |  |
| `state_safety_neg` | `safety_bypasses` | Unsafe Constructs (sprintf/strcpy/void*/any) | 8.4% | 17.2% | `sprintf`, `void *`, `catch (...)`, `any`, `pass`, `<any>` |
| `state_danger` | `high_risk_execution` | Process Exit, Eval & Shell Execution | 0.9% | 3.2% | `exit(`, `abort(`, `exit (`, `sys.exit`, `new function`, `eval` |
| `state_flux` | `state_mutation` | State Mutation | 39.1% | 40.9% | `i++`, `res =`, `.push_back(`, `.append(`, `val =`, `.push(` |
| `state_graveyard` | `dead_code` | Commented-Out Code | <0.1% | 2.2% |  |
| `state_unreferenced` | `unreferenced_by_name` | Unreferenced Definitions | 0 | 29.9% |  |
| `state_slop_duplicates` | `duplicate_logic` | Duplicated Logic | 0 | 2.1% |  |
| `state_planned_debt` | `planned_debt` | TODO / Stub Markers | 0.3% | 5.2% | `todo`, `implement`, `stub` |
| `state_fragile_debt` | `fragile_debt` | FIXME / HACK Markers | 0.3% | 3.6% | `bug`, `wtf` |
| `state_bailout_hits` | `panics_and_aborts` | Error Exits (raise/throw/abort) | 5.7% | 11.3% | `return -1`, `exit`, `abort`, `raise`, `throw`, `os.exit` |
| `state_halt_hits` | `thread_sleeps` | Sleeps & Timed Waits | 0.3% | 1.5% | `sleep`, `usleep`, `delay`, `time.sleep`, `settimeout`, `setinterval` |
| `state_heat_triggers` | `reflection_metaprogramming` | Metaprogramming (Macros, Reflection, goto) | 3.5% | 15.3% | `goto`, `#define o`, `#define h`, `@classmethod`, `getattr`, `prototype` |
| `state_pointers` | `pointers` | Pointers & Addressing | 29.5% | 18.7% | `->`, `size_t`, `*reinterpret_cast`, `*string`, `&instructions`, `*const` |
| `state_memory_alloc` | `memory_alloc` | Manual Memory Allocation | 2.5% | 5.2% | `malloc(`, `malloc (`, `new`, `alloca`, `new arraybuffer`, `make(` |
| `state_cast_hits` | `explicit_casts` | Explicit Casts & Conversions | 7.7% | 13.9% | `(int)f`, `(int)c`, `reinterpret_cast`, `static_cast`, `int(`, `str(` |
| `state_print_hits` | `debug_prints` | Print / Console Output | 2.3% | 6.7% | `fprintf`, `printf`, `print(`, `input(`, `console.warn`, `console.error` |
| `bitwise_ops` | `bitwise_ops` | Bitwise Operations | 5.9% | 12.6% |  |
| `arch_io` | `io` | File & Network I/O | 3.0% | 9.5% | `write (`, `read (`, `std::filesystem`, `os.`, `open`, `path` |
| `arch_api` | `api` | Public / Exported Surface | 36.8% | 48.9% | `typedef`, `extern`, `public:`, `def update`, `def routeto`, `export` |
| `arch_concurrency` | `concurrency` | Async & Concurrency | 6.6% | 8.8% | `thread_local`, `std::thread`, `std::mutex`, `async`, `await`, `promise` |
| `arch_import` | `import` | Imports & Includes | 1.3% | 54.9% | `#include <string.h>`, `#include <stdio.h>`, `import t`, `import s`, `import { monoid } from`, `import { option } from` |
| `arch_ui_framework` | `ui_framework` | UI Components | 1.4% | 6.1% | `<e1`, `<e2`, `<reactclientvalue`, `<transition`, `model`, `servehttp` |
| `arch_globals` | `globals` | Global State | 2.0% | 14.9% | `static`, `static thread_local`, `global _`, `os.environ`, `document.`, `process.env` |
| `arch_ipc` | `ipc_rpc_bridges` | Processes, IPC & RPC | 0.5% | 1.9% | `mmap`, `accept`, `subprocess`, `multiprocessing`, `worker`, `child_process` |
| `arch_ssr_boundaries` | `ssr_boundaries` | Server Response Boundaries | 0.1% | 0.7% | `jsonresponse`, `http.responsewriter`, `response` |
| `arch_events` | `events` | Event Emitters | 0.8% | 2.6% | `select`, `slot`, `emit`, `send`, `.emit(`, `.on(` |
| `arch_scientific` | `scientific` | Math & Scientific Calls | 1.0% | 3.7% | `i`, `log`, `math.`, `random`, `f32`, `f64` |
| `arch_dependency_injection` | `dependency_injection` | Dependency Injection | 0.6% | 3.7% | `depends`, `provide`, `resolve`, `register`, `@inject`, `@bean` |
| `arch_inline_asm` | `inline_asm` | Inline Assembly | 0.1% | 0.3% | `asm(` |
| `arch_hardware` | `hardware_bridge` | Hardware / Serial Access | <0.1% | <0.1% | `import serial` |
| `arch_crypto` | `cryptography` | Cryptography Libraries | <0.1% | 0.2% | `import hashlib`, `from 'crypto`, `require('tls`, `require('crypto` |
| `arch_serialization` | `serialization_parsing` | Serialization & Parsing (JSON etc.) | 0.4% | 1.4% | `serializetostring`, `json.stringify`, `json.parse`, `json.marshal`, `serialize`, `json_decode` |
| `arch_regex` | `regex_execution` | Regex & String Matching | 0.7% | 2.7% | `re.compile`, `re.split`, `.split(`, `.replace(`, `.matches(`, `.matchstring` |
| `arch_time` | `time_date_logic` | Time & Date Logic | 0.9% | 3.0% | `time_t`, `strftime`, `time.sleep`, `time.time`, `settimeout`, `cleartimeout` |
| `arch_sys_config` | `system_config_mutation` | System Configuration Changes | <0.1% | <0.1% |  |
| `def_safety` | `safety` | Defensive Checks (assert/try/guards) | 15.1% | 23.9% | `assert`, `size_t`, `std::optional`, `noexcept`, `try`, `isinstance` |
| `def_doc` | `doc` | Documentation Blocks | 0.2% | 24.8% | `@type`, `#[doc(hidden)]`, `#[doc(inline)]`, `@deprecated` |
| `def_test` | `test` | Test Assertions | 13.0% | 12.8% | `assert_dict_locked`, `assert_consistent`, `def test_`, `patch`, `assert(`, `expect(` |
| `def_ownership` | `ownership` | Authorship Tags | <0.1% | 2.7% |  |
| `def_spec_exposure` | `spec_exposure` | Spec Reference Tags | <0.1% | <0.1% | `[special___enter__]`, `[special___exit__]` |
| `def_telemetry` | `telemetry` | Structured Logging | 0.5% | 1.2% | `logger.warning`, `logger.debug`, `log.info`, `warn!`, `log::error!` |
| `def_sync_locks` | `sync_locks` | Locks & Synchronization | 0.7% | 1.9% | `lock`, `mutex`, `condition` |
| `def_freeze_hits` | `immutability_locks` | Immutability (const/readonly/final) | 11.9% | 18.5% | `const`, `restrict`, `constexpr`, `frozenset`, `final`, `readonly` |
| `def_cleanup` | `cleanup` | Resource Cleanup (close/free/dispose) | 1.9% | 5.2% | `fclose(`, `close (`, `free(`, `reset(`, `close(`, `dispose(` |
| `def_encapsulation` | `encapsulation` | Private Scope (private/static/_name) | 19.8% | 21.2% | `static`, `private:`, `protected:`, `def _get_value`, `private`, `protected` |
| `def_listeners` | `listeners` | Event Listeners & Handlers | 1.1% | 4.2% | `handler`, `callback`, `connect`, `on`, `effect`, `addeventlistener` |
| `def_test_skip` | `test_skip` | Mocks, Stubs & Skipped Tests | 0.5% | 1.4% | `mock.`, `stub`, `describe.skip`, `mock`, `mock(`, `spy(` |
| `def_auth` | `auth_middleware` | Authentication & Permission Checks | <0.1% | <0.1% | `pam_acct_mgmt(`, `.checkpermission(`, `gate::allows(` |
| `llm_api` | `llm_api` | Cloud LLM API Calls | <0.1% | <0.1% |  |
| `llm_orchestrator` | `llm_orchestrator` | LLM Orchestration Frameworks | <0.1% | <0.1% |  |
| `llm_vector_store` | `llm_vector_store` | Vector Database Use | 0 | <0.1% |  |
| `llm_local_compute` | `llm_local_compute` | Local Inference & Tensor Libraries | 0 | <0.1% |  |
| `ml_traditional` | `ml_traditional` | Classical Machine Learning | <0.1% | <0.1% |  |
| `dl_frameworks` | `dl_frameworks` | Deep Learning Frameworks | <0.1% | 0.2% |  |
| `lazy_evaluation` | `lazy_evaluation` | Lazy Evaluation & Generators | 0.3% | 0.7% |  |
| `vectorized_math` | `vectorized_math` | Vectorized / Tensor Math | <0.1% | 0.1% |  |
| `lit_code_blocks` | `lit_code_blocks` | Docs: Code Examples | 0 | 1.7% |  |
| `lit_diagrams` | `lit_diagrams` | Docs: Diagrams | 0 | <0.1% |  |
| `lit_headers` | `lit_headers` | Docs: Section Headers | 0 | 2.4% |  |
| `lit_links` | `lit_links` | Docs: Links | 0 | 1.6% |  |
| `threat_obfuscated` | `sec_reflection_metaprogramming` | Security: Obfuscated / Dynamic Code | 0 | 0.4% |  |
| `threat_bypasses` | `sec_safety_bypasses` | Security: Safety Bypasses | 0 | <0.1% |  |
| `threat_network_hooks` | `sec_io` | Security: Network & I/O Hooks | 0 | 0.6% |  |
| `threat_eval_exec` | `sec_high_risk_execution` | Security: Eval / Exec | 0 | 0.5% |  |
| `threat_env_mutation` | `sec_state_mutation` | Security: Environment Mutation | 0 | 0.2% |  |
| `sec_dead_code` | `sec_dead_code` | Security: Commented-Out Executable Code | 0 | 0.6% |  |
| `threat_crypto_math` | `sec_bitwise_ops` | Security: Bitwise / Crypto-Style Math | 0 | <0.1% |  |
| `threat_stego_imports` | `sec_shadow_imports` | Security: Unusual Imports | 0 | <0.1% |  |
| `threat_homoglyphs` | `sec_homoglyphs` | Security: Homoglyph Identifiers | 0 | <0.1% |  |
| `threat_private_info` | `sec_hardcoded_secrets` | Security: Hard-Coded Secrets | 0 | 0.2% |  |
| `threat_extension_mismatch` | `sec_extension_mismatch` | Security: File Extension Mismatch | 0 | 0 | not a regex: set by the disguised-executable check (#4126) when an inert extension (`.png`, `.txt`, ...) starts with executable magic bytes; no population file trips it |
| `threat_entropy` | `sec_entropy` | Security: High-Entropy Strings | 0 | 0.4% |  |
| `threat_tainted_injection` | `sec_tainted_injection` | Security: Tainted Input Reaching a Sink | 0 | 0 | none: taint tracking removed (#3101) after measuring about 0% precision and recall |
| `prompt_injection` | `prompt_injection` | Security: Prompt Injection (detector removed) | 0 | 0 |  |
| `agentic_rce` | `agentic_rce` | Security: Agentic RCE (detector removed) | 0 | 0 |  |
| `sec_unicode_steganography` | `sec_unicode_steganography` | Security: Invisible Unicode | 0 | <0.1% |  |
| `sec_self_propagation` | `sec_self_propagation` | Security: Self-Copying (Worm Pattern) | 0 | <0.1% |  |
| `threat_db_sinks` | `sec_db_hooks` | Security: Raw Database Calls | 0 | 0.8% |  |
| `threat_api_near_db_sink` | `sec_amplified_sql_injection` | Security: Public API Near Raw DB Call | 0 | 0.2% |  |

## Not measured per function ([#8012](https://github.com/squid-protocol/gitgalaxy/issues/8012))

These `function_data` columns are zero for every function: the signal is never in the per-function hit vector. A `0` there
means "not measured at this level". Use the `file_data` column. `FUNCTION_LEVEL_ABSENT_SIGNALS` in `analysis_lens.py` is
the machine-readable list. Removing the columns from `function_data` waits for the next archetype retrain. Its reason
string for `sec_extension_mismatch` still says "never set"; the table below gives the correct reason; the code text is tracked in #8435.

| column | display name | why |
|---|---|---|
| `struct_tabs` | Tab Indentation | file-level only: naming/indentation style is tallied per file |
| `struct_spaces` | Space Indentation | file-level only: naming/indentation style is tallied per file |
| `struct_camel_case` | camelCase Names | file-level only: naming/indentation style is tallied per file |
| `struct_snake_case` | snake_case Names | file-level only: naming/indentation style is tallied per file |
| `struct_pascal_case` | PascalCase Names | file-level only: naming/indentation style is tallied per file |
| `struct_upper_case` | UPPER_CASE Names | file-level only: naming/indentation style is tallied per file |
| `struct_short_vars` | Short Names | file-level only: naming/indentation style is tallied per file |
| `struct_long_vars` | Long Names | file-level only: naming/indentation style is tallied per file |
| `struct_var_decl` | Variable Declarations | file-level only: the declaration census feeds the file encapsulation ratio |
| `state_slop_duplicates` | Duplicated Logic | file-level only: duplicate detection compares whole files |
| `state_unreferenced` | Unreferenced Definitions | file-level only: a cross-file name census (docs/unreferenced_by_name_contract.md) |
| `llm_vector_store` | Vector Database Use | file-level only: an import-based sensor, and imports sit outside function bodies |
| `llm_local_compute` | Local Inference & Tensor Libraries | file-level only: an import-based sensor, and imports sit outside function bodies |
| `lit_code_blocks` | Docs: Code Examples | file-level only: literature sensors run on documentation files |
| `lit_diagrams` | Docs: Diagrams | file-level only: literature sensors run on documentation files |
| `lit_headers` | Docs: Section Headers | file-level only: literature sensors run on documentation files |
| `lit_links` | Docs: Links | file-level only: literature sensors run on documentation files |
| `threat_obfuscated` | Security: Obfuscated / Dynamic Code | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_bypasses` | Security: Safety Bypasses | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_network_hooks` | Security: Network & I/O Hooks | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_eval_exec` | Security: Eval / Exec | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_env_mutation` | Security: Environment Mutation | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `sec_dead_code` | Security: Commented-Out Executable Code | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_crypto_math` | Security: Bitwise / Crypto-Style Math | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_stego_imports` | Security: Unusual Imports | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_homoglyphs` | Security: Homoglyph Identifiers | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_private_info` | Security: Hard-Coded Secrets | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_entropy` | Security: High-Entropy Strings | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `sec_unicode_steganography` | Security: Invisible Unicode | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `sec_self_propagation` | Security: Self-Copying (Worm Pattern) | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_db_sinks` | Security: Raw Database Calls | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_api_near_db_sink` | Security: Public API Near Raw DB Call | file-level only: the security lens runs file-wide, never in the per-function hit vector |
| `threat_extension_mismatch` | Security: File Extension Mismatch | file-level only: set by the disguised-executable check (#4126, `security_lens.detect_disguised_executable`, tested in `test_disguised_executable_4126.py`) on whole-file magic bytes; zero in every row of the v2.12.0 population because no file there trips it, not because it is unset |
| `threat_tainted_injection` | Security: Tainted Input Reaching a Sink | never set: taint tracking removed (#3101) after it measured about 0% precision and about 0% recall on the corpus; positional placeholder only |
| `prompt_injection` | Security: Prompt Injection (detector removed) | never set: detector removed (#1020), positional placeholder only |
| `agentic_rce` | Security: Agentic RCE (detector removed) | never set: detector removed (#1020), positional placeholder only |
