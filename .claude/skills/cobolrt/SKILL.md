---
name: cobolrt
description: Best practices and engineering rules for developing, optimizing, and auditing cobolrt (gitgalaxy/tools/cobol_to_java/det/cobolrt) — performance (ns/op, primitive fast paths, CPU-time benchmarking), natural Java & anti-duplication (#8486, #4715), thread-safety/options (#4714), rule catalogue & API surface (#4711, #4718), and rule/quirk telemetry (#4713, #4716). Use when editing cobolrt Java classes, det translator emissions, or cobolrt_rules.json / cobolrt_api.json.
---

# cobolrt Runtime Engineering Skill

`cobolrt` is the Java runtime shipped inside every translated COBOL port (`gitgalaxy/tools/cobol_to_java/det/cobolrt`). Unlike traditional transpiler runtimes (`libcobj` in `opensourcecobol4j`, `NacaRT`) that wrap every variable in heavy runtime objects forever, `cobolrt` is designed to be **provably faithful, fast, transparent, and exit-routed** (customers can simplify away from it using telemetry evidence).

## Core Engineering Rules

### 1. Measure `ns/op` with CPU Time & Prefer Primitive Fast Paths (#4717, #8423)
- **Never guess performance, and never assert raw wall-clock time in tests.** Use `tests/tools/cobolrt_bench.py` (`ThreadMXBean.getCurrentThreadCpuTime()`, JIT warmup, best-of-3 rounds). Adding wall-clock difference asserts in `tests/**/test_*.py` is blocked by `tests/tools/test_no_raw_wall_clock_timing_8423.py`.
- **Avoid per-byte / per-op heap allocations on hot paths:**
  - Never call `new String(new byte[]{b}, cs)` or `String.valueOf(c).getBytes(cs)` in a loop — use cached `CharsetTable` / `Lossless.decodeByte` / `encodeChar` lookups.
  - Precompute `POW10` tables instead of calling `BigInteger.TEN.pow(digits)`.
  - Use `long` arithmetic for `<= 18` digits (`<= 9` packed bytes, `<= 8` binary bytes) and `BigDecimal.valueOf(long, scale)` instead of `BigInteger` + `Codec.Num` + `new BigDecimal(BigInteger, scale)`, falling back to `BigInteger` only outside those bounds.
- **Prove 0 semantic diffs:** Every fast path must pass A/B fuzzing against the `BigInteger` reference (`tests/cobol_mainframe/test_cobolrt_perf.py`) and the GnuCOBOL equivalence suite (`EQUIVALENCE_E2E=1`).

### 2. Aim for Natural Java & Hoist Shared Shims (#8486, #4715)
- **Never duplicate runtime shims across generated `*Service.java` files.** Shared helpers (`DetCics.loadCommarea`, `restoreCommarea`, `eibCalen`, `resolveCondition`, `paragraph`, etc.) belong in `cobolrt`, not emitted inline per service. Enforced by `tests/tools/test_no_duplicated_port_shims_8486.py`.
- **Boundary Anti-Corruption Layer (ACL):** Keep EBCDIC/packed/zoned byte decoding at I/O, `COMMAREA`, and file/screen boundaries. Inside business logic, prefer lifted plain Java types (`long`, `BigDecimal`, `String`) whenever `REDEFINES` and non-digit quirks are provably absent (#4715).
- **Keep generated call sites readable:** Name runtime methods after what they do in Java/COBOL domain terms, and keep per-service boilerplate minimal.

### 3. Thread-Safety & Explicit Options (#4714)
- **Avoid global `static volatile` state for per-program options** and avoid mutable singleton state on `@Service` beans under concurrent CICS/Spring execution. Scope options (`TRUNC`, `NUMPROC`, `ARITH`, `COMP-5`, code page) and task/working storage per task/profile context.

### 4. Rule Catalogue, API Surface & Fail-Loudly Discipline (#4711, #4718)
- **Every semantic rule carries `// [rule RT-...]`** above its implementation and a matching entry in `docs/language_status/cobolrt_rules.json` (15 families, 194 rules). Every internal helper method must be listed in its family's `plumbing` list.
- **Keep `docs/language_status/cobolrt_api.json` in sync:** Run `python tests/tools/cobolrt_api.py generate` (and `--promote-used` when adding emitted public helpers).
- **Fail loudly, never silently:** Unsupported constructs, unmodelled option combinations, or non-preferred signs under `NUMPROC(PFD)` must throw a named exception (`Hole` / `UnsupportedOperationException`), never guess.

### 5. Instrument Quirk Paths with Zero-Overhead Telemetry (#4713, #4716)
- **Off by default:** `RuleTelemetry.hit("RT-...")` is a single volatile read (`if (!enabled) return;`) when off, adding zero measurable overhead in production.
- **Keyed by catalogue ID:** Instrument COBOL quirk paths (overflow truncation, non-digit zoned reads/moves, zero-divisor NaN, overpunched signs, intermediate alignment) so `tests/tools/cobolrt_exit_report.py` can generate both `#4713` rule-usage evidence and `#4716` safe plain-Java simplification reports.

## Verification Checklist

Run these after any `cobolrt` or `det` emission change:

```bash
# 1. API surface & rule catalogue consistency
.venv/bin/python tests/tools/cobolrt_api.py --check
.venv/bin/python tests/tools/cobolrt_rules.py --check

# 2. Unit, parity, telemetry, and guard tests
.venv/bin/pytest \
  tests/cobol_mainframe/test_cobolrt_api.py \
  tests/cobol_mainframe/test_cobolrt_rules.py \
  tests/cobol_mainframe/test_cobolrt_perf.py \
  tests/cobol_mainframe/test_cobolrt_telemetry.py \
  tests/tools/test_no_duplicated_port_shims_8486.py \
  tests/tools/test_no_raw_wall_clock_timing_8423.py

# 3. CPU-time microbenchmark (when touching hot paths)
.venv/bin/python tests/tools/cobolrt_bench.py --mode both --iters 200000 --fuzz 10000
```
