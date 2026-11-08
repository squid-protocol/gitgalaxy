# Rule overlaps: one token, two keyword rules

[gitgalaxy#8010](https://github.com/squid-protocol/gitgalaxy/issues/8010). When two keyword rules match the identical
span, the two signals co-occur by definition, so function-level pair statistics must not read that as real
co-occurrence. `tests/extraction/languages/test_rule_overlap_guard_8010.py` pins every such pair: a new shared span
fails the test unless it is added there as intended or review, and a listed pair that stops reproducing fails too.

| language | token | rules | disposition |
|---|---|---|---|
| c | `size_t` | pointers, safety | leak, fixed (#8024): removed from `safety` |
| python | `pass` | safety_bypasses, structural_boundaries | leak, fixed (#8024): only `except ...: pass` is a bypass |
| php | `exit`, `die` | debug_prints, panics_and_aborts | leak, fixed (#8024): aborts, not prints |
| typescript | class `extends` | generics, structural_boundaries | leak, fixed with #8011 |
| python, typescript, javascript, csharp | `await` | concurrency, structural_boundaries | intended |
| php | `require`, `require_once` | import, structural_boundaries | intended |
| php, typescript, javascript, csharp | `??` | branch, safety | intended (both a branch and a null guard) |
| csharp | `?.` | branch, safety | intended |
| typescript, javascript | `export` | api, structural_boundaries | intended (keyword and public surface) |
| rust | `where` | generics, structural_boundaries | intended |
| rust | `#[cfg(test)]` | decorators, test | intended |
| csharp | `Interlocked` | concurrency, sync_locks | intended |
| c | `typedef` | api, structural_boundaries | review |
| typescript, javascript | `setTimeout` | concurrency, thread_sleeps, time_date_logic | review (three rules) |
| typescript | `stub` | planned_debt, test_skip | review |
| javascript | `on` | events, listeners | review |
| rust | `panic!` | high_risk_execution, panics_and_aborts | review |
| rust | `macro_rules!` | macros, reflection_metaprogramming | review |
| rust | `#[doc(hidden)]` | decorators, doc | review |
| csharp | `=>` | closures, structural_boundaries | review (expression-bodied members are not closures) |
| go | `os.Exit` | high_risk_execution, panics_and_aborts | review |
| go | `exec.Command` | high_risk_execution, ipc_rpc_bridges | review |

Review rows are open: deciding one changes a rule and moves goldens, so each is its own slice.
