# Missing-keyword mining report (#8863, step 3)

Report only: no keyword changed. Every row is a question for step 4 (time the candidate on keyword-rosetta and language-crucible), not a
verdict: the oracle's callee lists are its own reading of the family contract.

Regenerate (heavy: it scans the pinned crucible; run it under `tests/tools/box/heavy-run.sh` with `LANGUAGE_CRUCIBLE_PATH` at the pin):

    python tests/tools/family_missing_keywords.py --sweep --top 15 --out docs/family_missing_keywords.md   # then re-add this preface

Measured on language-crucible v1.8.0 (`<crucible>/data`, scanned as the golden masters scan it), engine at `781ffa5325`.

| Class | Status |
|---|---|
| every family `family_oracle.score()` scores, per oracle language (Python and the tree-sitter set) | mined below |
| distinct functions per token (`functions`), beside occurrences (`count`) | in the table |
| languages with no token oracle (COBOL; JCL, HLASM, PL/I, REXX, ABAP, SQL dialects) | not mined: no parser oracle to name the construct |
| timing each candidate token on keyword-rosetta and language-crucible | remaining slice (step 4) |

How to read it: bitwise_ops dominates because the oracle counts every operator-position `&`, `|`, `<<`, so the missed tokens are operators,
not keywords; `c / bitwise_ops` (212 of 414 missed) and `cpp / bitwise_ops` (99 of 112) are the largest cells. A cell with a small
`functions` count and a large `count` is one function repeating a token.

Tokens the parser oracle saw in functions where the family read 0: candidate additions, each to be timed on keyword-rosetta and language-crucible before merging. Count is occurrences; functions is the distinct missed functions holding the token.

## Cells with missed functions (53)

### c / struct_branch: 2 of 1801 missed (recall 1.00, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `if_statement` | 1 | 1 | 0.5 |

### c / struct_short_circuit: 8 of 711 missed (recall 0.99, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `&&` | 35 | 5 | 4.38 |
| `\|\|` | 16 | 7 | 2.0 |

### c / state_bailout_hits: 1 of 29 missed (recall 0.97, over-counts)

| token | count | functions | per fn |
|---|---|---|---|
| `abort` | 1 | 1 | 1.0 |

### c / bitwise_ops: 212 of 414 missed (recall 0.49, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `&` | 411 | 192 | 1.94 |
| `\|` | 41 | 23 | 0.19 |
| `<<` | 1 | 1 | 0.0 |
| `~` | 1 | 1 | 0.0 |

### c / state_print_hits: 2 of 43 missed (recall 0.95, over-counts)

| token | count | functions | per fn |
|---|---|---|---|
| `fprintf` | 8 | 1 | 4.0 |
| `printf` | 1 | 1 | 0.5 |

### cpp / struct_short_circuit: 4 of 244 missed (recall 0.98, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `\|\|` | 6 | 3 | 1.5 |
| `&&` | 2 | 2 | 0.5 |

### cpp / bitwise_ops: 99 of 112 missed (recall 0.12, both)

| token | count | functions | per fn |
|---|---|---|---|
| `<<` | 430 | 61 | 4.34 |
| `&` | 58 | 34 | 0.59 |
| `\|` | 52 | 11 | 0.53 |
| `>>` | 3 | 3 | 0.03 |

### cpp / arch_io: 11 of 12 missed (recall 0.08, both)

| token | count | functions | per fn |
|---|---|---|---|
| `bind` | 9 | 4 | 0.82 |
| `open` | 4 | 4 | 0.36 |
| `write` | 3 | 2 | 0.27 |
| `connect` | 1 | 1 | 0.09 |

### csharp / struct_decorators: 1 of 13 missed (recall 0.92, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `SuppressMessage` | 1 | 1 | 1.0 |

### csharp / bitwise_ops: 20 of 22 missed (recall 0.09, both)

| token | count | functions | per fn |
|---|---|---|---|
| `\|=` | 15 | 10 | 0.75 |
| `&` | 10 | 5 | 0.5 |
| `\|` | 5 | 3 | 0.25 |
| `&=` | 2 | 2 | 0.1 |

### go / state_bailout_hits: 2 of 96 missed (recall 0.98, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `log.Fatalf` | 5 | 2 | 2.5 |

### go / bitwise_ops: 73 of 122 missed (recall 0.40, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `&` | 73 | 49 | 1.0 |
| `\|` | 57 | 30 | 0.78 |
| `\|=` | 20 | 10 | 0.27 |

### java / struct_decorators: 21 of 474 missed (recall 0.96, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `@Nullable` | 19 | 19 | 0.9 |
| `@NotNull` | 2 | 2 | 0.1 |

### java / bitwise_ops: 10 of 10 missed (recall 0.00, dead)

| token | count | functions | per fn |
|---|---|---|---|
| `\|` | 7 | 7 | 0.7 |
| `\|=` | 6 | 3 | 0.6 |

### javascript / bitwise_ops: 63 of 71 missed (recall 0.11, both)

| token | count | functions | per fn |
|---|---|---|---|
| `\|` | 50 | 38 | 0.79 |
| `&` | 43 | 29 | 0.68 |
| `\|=` | 29 | 21 | 0.46 |

### javascript / arch_regex: 2 of 36 missed (recall 0.94, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `regex-literal` | 2 | 2 | 1.0 |
| `test` | 2 | 2 | 1.0 |

### lua / struct_short_circuit: 1 of 152 missed (recall 0.99, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `and` | 2 | 1 | 2.0 |

### lua / struct_closures: 1 of 77 missed (recall 0.99, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `function_definition` | 1 | 1 | 1.0 |

### lua / state_print_hits: 2 of 51 missed (recall 0.96, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `io.stderr.write` | 2 | 2 | 1.0 |

### lua / arch_regex: 23 of 87 missed (recall 0.74, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `*.match` | 13 | 12 | 0.57 |
| `*.gsub` | 12 | 7 | 0.52 |
| `*.gmatch` | 9 | 6 | 0.39 |
| `:find` | 5 | 3 | 0.22 |

### lua / arch_io: 7 of 14 missed (recall 0.50, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `*.write` | 3 | 3 | 0.43 |
| `*.read` | 2 | 2 | 0.29 |
| `loadfile` | 1 | 1 | 0.14 |
| `os.remove` | 1 | 1 | 0.14 |

### php / struct_closures: 5 of 102 missed (recall 0.95, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `anonymous_function` | 5 | 5 | 1.0 |

### php / state_print_hits: 1 of 18 missed (recall 0.94, over-counts)

| token | count | functions | per fn |
|---|---|---|---|
| `echo_statement` | 2 | 1 | 2.0 |

### php / arch_regex: 2 of 116 missed (recall 0.98, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `preg_grep` | 4 | 2 | 2.0 |

### php / arch_time: 5 of 24 missed (recall 0.79, misses)
(the saved result was capped at 5 tokens: rerun with a larger --top)

| token | count | functions | per fn |
|---|---|---|---|
| `microtime` | 2 | 2 | 0.4 |
| `checkdate` | 1 | 1 | 0.2 |
| `datetimezone` | 1 | 1 | 0.2 |
| `gmdate` | 1 | 1 | 0.2 |
| `mktime` | 1 | 1 | 0.2 |

### php / arch_io: 7 of 18 missed (recall 0.61, both)

| token | count | functions | per fn |
|---|---|---|---|
| `unlink` | 3 | 3 | 0.43 |
| `mkdir` | 1 | 1 | 0.14 |
| `opendir` | 1 | 1 | 0.14 |
| `readdir` | 1 | 1 | 0.14 |
| `scandir` | 1 | 1 | 0.14 |
| `touch` | 1 | 1 | 0.14 |

### python / struct_comprehensions: 41 of 198 missed (recall 0.79, both)

| token | count | functions | per fn |
|---|---|---|---|
| `map` | 11 | 11 | 0.27 |
| `reduce` | 3 | 1 | 0.07 |
| `filter` | 1 | 1 | 0.02 |

### python / arch_io: 30 of 72 missed (recall 0.58, both)
(the saved result was capped at 5 tokens: rerun with a larger --top)

| token | count | functions | per fn |
|---|---|---|---|
| `write` | 21 | 19 | 0.7 |
| `read` | 11 | 7 | 0.37 |
| `readline` | 4 | 2 | 0.13 |
| `listdir` | 2 | 2 | 0.07 |
| `mkdir` | 2 | 2 | 0.07 |

### python / arch_regex: 3 of 51 missed (recall 0.94, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `sub` | 4 | 2 | 1.33 |
| `escape` | 1 | 1 | 0.33 |

### python / arch_time: 32 of 48 missed (recall 0.33, both)

| token | count | functions | per fn |
|---|---|---|---|
| `ticks_ms` | 31 | 13 | 0.97 |
| `ticks_diff` | 23 | 9 | 0.72 |
| `sleep` | 10 | 6 | 0.31 |
| `utcnow` | 9 | 7 | 0.28 |
| `sleep_ms` | 7 | 7 | 0.22 |
| `ticks_us` | 5 | 3 | 0.16 |
| `time` | 4 | 3 | 0.12 |
| `gmtime` | 3 | 2 | 0.09 |
| `now` | 2 | 2 | 0.06 |
| `ticks_add` | 2 | 2 | 0.06 |
| `sleep_us` | 1 | 1 | 0.03 |
| `split` | 1 | 1 | 0.03 |

### python / state_danger: 6 of 17 missed (recall 0.65, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `exit` | 6 | 4 | 1.0 |
| `abort` | 1 | 1 | 0.17 |
| `system` | 1 | 1 | 0.17 |

### python / state_halt_hits: 9 of 20 missed (recall 0.55, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `sleep` | 13 | 9 | 1.44 |

### python / state_cast_hits: 4 of 279 missed (recall 0.99, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `bytearray` | 5 | 4 | 1.25 |

### python / bitwise_ops: 8 of 64 missed (recall 0.88, over-counts)

| token | count | functions | per fn |
|---|---|---|---|
| `BitOr` | 8 | 8 | 1.0 |

### python / def_telemetry: 140 of 144 missed (recall 0.03, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `debug` | 198 | 52 | 1.41 |
| `info` | 116 | 64 | 0.83 |
| `error` | 85 | 54 | 0.61 |
| `warn` | 32 | 20 | 0.23 |
| `warning` | 22 | 17 | 0.16 |
| `exception` | 19 | 16 | 0.14 |
| `critical` | 1 | 1 | 0.01 |

### python / def_sync_locks: 10 of 11 missed (recall 0.09, both)

| token | count | functions | per fn |
|---|---|---|---|
| `release` | 10 | 8 | 1.0 |
| `acquire` | 2 | 2 | 0.2 |

### python / arch_globals: 8 of 44 missed (recall 0.82, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `global` | 8 | 8 | 1.0 |

### python / def_cleanup: 30 of 370 missed (recall 0.92, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `with` | 49 | 28 | 1.63 |
| `del` | 4 | 4 | 0.13 |
| `remove` | 4 | 4 | 0.13 |
| `finally` | 1 | 1 | 0.03 |

### ruby / struct_closures: 1 of 49 missed (recall 0.98, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `block` | 1 | 1 | 1.0 |

### ruby / state_bailout_hits: 1 of 14 missed (recall 0.93, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `exit` | 1 | 1 | 1.0 |

### ruby / arch_regex: 8 of 22 missed (recall 0.64, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `regex-literal` | 27 | 8 | 3.38 |

### ruby / arch_time: 8 of 10 missed (recall 0.20, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `Time.` | 9 | 8 | 1.12 |

### ruby / arch_io: 6 of 15 missed (recall 0.60, both)

| token | count | functions | per fn |
|---|---|---|---|
| `*.read` | 3 | 3 | 0.5 |
| `*.mkpath` | 2 | 2 | 0.33 |
| `*.open` | 1 | 1 | 0.17 |

### rust / struct_short_circuit: 4 of 37 missed (recall 0.89, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `&&` | 3 | 3 | 0.75 |
| `\|\|` | 1 | 1 | 0.25 |

### rust / state_bailout_hits: 2 of 66 missed (recall 0.97, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `todo!` | 4 | 2 | 2.0 |

### rust / bitwise_ops: 26 of 47 missed (recall 0.45, both)

| token | count | functions | per fn |
|---|---|---|---|
| `\|=` | 17 | 7 | 0.65 |
| `&` | 12 | 10 | 0.46 |
| `\|` | 12 | 11 | 0.46 |

### shell / arch_io: 40 of 236 missed (recall 0.83, over-counts)

| token | count | functions | per fn |
|---|---|---|---|
| `mkdir` | 27 | 21 | 0.68 |
| `rm` | 17 | 11 | 0.42 |
| `touch` | 10 | 9 | 0.25 |
| `ln` | 8 | 7 | 0.2 |
| `cp` | 5 | 5 | 0.12 |
| `mv` | 5 | 4 | 0.12 |
| `read` | 2 | 2 | 0.05 |
| `mapfile` | 1 | 1 | 0.03 |
| `mktemp` | 1 | 1 | 0.03 |

### swift / struct_closures: 18 of 46 missed (recall 0.61, misses)

| token | count | functions | per fn |
|---|---|---|---|
| `lambda_literal` | 27 | 18 | 1.5 |

### typescript / struct_branch: 14 of 3475 missed (recall 1.00, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `if_statement` | 321 | 5 | 22.93 |
| `switch_case` | 223 | 1 | 15.93 |
| `ternary_expression` | 98 | 13 | 7.0 |
| `for_in_statement` | 10 | 2 | 0.71 |
| `while_statement` | 7 | 2 | 0.5 |
| `for_statement` | 3 | 2 | 0.21 |

### typescript / struct_short_circuit: 2 of 2242 missed (recall 1.00, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `&&` | 167 | 3 | 83.5 |
| `\|\|` | 79 | 3 | 39.5 |

### typescript / bitwise_ops: 1196 of 1287 missed (recall 0.07, misses)
(the saved result was capped at 5 tokens: rerun with a larger --top)

| token | count | functions | per fn |
|---|---|---|---|
| `&` | 2680 | 915 | 2.24 |
| `\|` | 985 | 456 | 0.82 |
| `\|=` | 299 | 146 | 0.25 |
| `&=` | 33 | 16 | 0.03 |
| `~` | 8 | 2 | 0.01 |

### typescript / state_print_hits: 1 of 17 missed (recall 0.94, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `console.debug` | 1 | 1 | 1.0 |

### typescript / arch_regex: 1 of 34 missed (recall 0.97, ok)

| token | count | functions | per fn |
|---|---|---|---|
| `regex-literal` | 7 | 1 | 7.0 |
| `test` | 4 | 1 | 4.0 |


## Shared across languages

- `arch_io`: `mkdir` (30; php, python, shell), `write` (24; cpp, python), `read` (13; python, shell), `touch` (11; php, shell), `*.read` (5; lua, ruby)
- `arch_regex`: `regex-literal` (36; javascript, ruby, typescript), `test` (6; javascript, typescript)
- `bitwise_ops`: `|` (1209; c, cpp, csharp, go, java, javascript, rust, typescript), `&` (3287; c, cpp, csharp, go, javascript, rust, typescript), `|=` (386; csharp, go, java, javascript, rust, typescript), `<<` (431; c, cpp), `&=` (35; csharp, typescript), `~` (9; c, typescript)
- `struct_branch`: `if_statement` (322; c, typescript)
- `struct_short_circuit`: `&&` (207; c, cpp, rust, typescript), `||` (102; c, cpp, rust, typescript)

## Thin cells, not ranked (10)

c/arch_time (5 fn); cpp/state_halt_hits (1 fn); kotlin/struct_closures (3 fn); kotlin/struct_decorators (8 fn); lua/state_halt_hits (3 fn); ruby/bitwise_ops (4 fn); scala/arch_io (4 fn); shell/bitwise_ops (2 fn); typescript/struct_decorators (1 fn); typescript/arch_io (7 fn).
