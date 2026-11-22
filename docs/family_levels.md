---
description: "How GitGalaxy's keyword families are organised: narrow leaf families, computed composites, one oracle per leaf."
---
# Family levels

Decided 2026-11-21 (Eagle Eye milestone, #8863; first split: `branch` -> `branch` +
`short_circuit`, #8862). The family-validity chart showed that the broad families score worst,
and the reason is the same each time: one name covering several things that languages spell and
count differently. So:

1. **Leaf families** have a one-sentence contract naming one thing a parser can recognise, and are
   the only families the engine scans.
2. **Composite families** are arithmetic on leaves (`decision_points = branch + short_circuit`).
   They add no rule, so they inherit their leaves' validation, and existing consumers can keep a
   composite under the old name where the sum is what they meant.
3. **Every leaf gets a parser oracle** (`tests/tools/family_oracle*.py`) and a cell on the
   validity chart before its contract is called `stated`.

## The split order

| now | leaves | composite | why this one |
|---|---|---|---|
| `branch` | `branch` (constructs and arms), `short_circuit` (boolean operators) | `decision_points` | the 36-language disagreement behind #8905; done in this change |
| `bitwise_ops` (median 0.46) | `bit_shift`, `bit_mask` (and/or/xor/complement on values) | `bitwise_ops` | generics' `>>` and `&`/`|` between values are different questions (#8861, #8866) |
| `io` (0.39) | `io_file`, `io_network` | `io` | `IO` as a type, console, sockets and files fail for different reasons (#8904 Haskell) |
| `time_date_logic` (0.38) | `clock_read`, `date_format_parse`, `date_arith` | `time_date_logic` | sleeps are already `thread_sleeps` (#8859 `perf_counter`) |
| `closures` (0.59) | `anonymous_fn`, `nested_fn` | `closures` | lambdas and nested defs are counted differently per language (#8857, #8862) |
| `regex_execution` (0.63) | `regex_literal` (operator or literal form), `regex_call` (library call) | `regex_execution` | operators vs API calls, and the string-shielding decision (#8858, #2535) |

A split lands as its own PR: contract row and doc, leaf rules per language moved or narrowed with
a per-function equivalence check against the old family (`old == sum of leaves` except deliberate
changes, listed), tests, one golden re-bless, one oracle, and a chart row.
