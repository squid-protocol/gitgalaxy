# Description
Fixes #855

This PR introduces comprehensive hardening to the Fortran static analysis extraction rules (`func_start`, `class_start`, `args`, and `_dependency_capture`) to protect against Catastrophic Backtracking (ReDoS) vulnerabilities and to accurately support both Modern (F90+) and Legacy (F77) Fortran syntax edge cases.

## Multi-Agent Hardening Pipeline
This fix was developed using our rigorous 5-stage agent pipeline:
1. **Linguist Research**: Discovered that Fortran extraction was missing multi-line continuations (`&`), failed to parse modern Fortran's `VALUE` and `OPTIONAL` argument attributes, completely missed `SUBMODULE` parent dependency structures, and lacked support for `PURE`/`ELEMENTAL` prefixes in function declarations.
2. **Red Team Adversarial Testing**: Created highly pathological test payloads that successfully triggered Catastrophic Backtracking (ReDoS) in the existing `_dependency_capture` regex by inserting thousands of spaces between `USE` and module names. Also constructed lookalike structures like `print *, "subroutine foo()"` to test false positives.
3. **Engineering Implementation**: Eliminated the ReDoS vulnerability by replacing loose `.*` wildcards with strictly bounded whitespace checks, and refactored `func_start` and `args` regexes to capture the newly discovered modern Fortran attributes and continuations safely.
4. **QA Auditing**: Audited the results against the WRF codebase using `crucible_check.py`, confirming that the hardened regexes successfully identified previously missed dependencies and structurally bounded previously uncaptured modules, with no new false positives.

## Metrics & Limitations
- **Tests Created**: 32 adversarial test cases spanning legacy F77 up to modern Fortran.
- **Errors Found & Fixed**: Identified 1 severe ReDoS timeout vulnerability in `_dependency_capture`, plus 12 structural extraction errors (e.g. missing continuations, unparsed `VALUE`/`OPTIONAL` arguments).
- **Known Regex Limitations**: Fortran case-insensitivity coupled with un-expanded preprocessor macros (like C's `#ifdef`) can still sporadically obscure structural boundaries to a purely static regex. Legacy fixed-format F77 comments (starting with `c` or `*` at column 7) could theoretically interfere if wildly mis-spaced in string literals.

## Specific Rule Improvements:
- **`func_start`**: Now supports `DOUBLE COMPLEX`, `&` multi-line continuations, prefixes (`PURE`, `ELEMENTAL`, `RECURSIVE`), and precise length/kind parameter matching with `=` (e.g., `INTEGER(KIND=4)`).
- **`class_start`**: Expanded to correctly capture `SUBMODULE (parent) child` dependencies, while strictly preventing variable declarations like `TYPE(...)` from causing false-positive structural boundaries.
- **`args`**: Enhanced to correctly capture `VALUE` and `OPTIONAL` attribute modifiers that contribute to coupling mass.
- **`_dependency_capture`**: Eliminated a severe Catastrophic Backtracking (ReDoS) vulnerability in the capture of dependencies. Added support for `USE :: mod` syntax and submodule parent dependency extraction.
- **Golden Masters**: Safely regenerated `golden_master_zero_dep_audit.json` and `golden_master_audit.json` to reflect the significantly increased extraction precision across the Fortran ecosystem.

## Workflow Note
All extraction hardening work MUST be done on a side branch and merged back into `main` via PR. This ensures that CI checks, test suites, and multi-agent QA pipelines are run in isolation and prevent merging regressions directly into the main repository timeline.
