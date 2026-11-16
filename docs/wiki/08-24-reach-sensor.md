---
description: "> **Command:** `gitgalaxy reach SCAN_DB [--src ROOT]`. Who depends on a file: caller counts from the call graph, include counts for headers. Read-only, no change to scan output."
---
# Reach Sensor (Who Depends on This)

> **File Reference:** [`gitgalaxy/tools/sensors/reach.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/sensors/reach.py)
>
> **Command:** `gitgalaxy reach SCAN_DB [--src ROOT] [--callee NAME] [--top N] [--all-roles] [--rank-with-possible] [--json FILE]`
>
> **Metric:** The number of other files and functions that call into a file (and the callers of those callers, one hop out); for a header, the number of files that include it.
>
> **Summary:** Answers "if I change this, how much code is on the receiving end?" from the call graph a scan already stores. A count, not a score, with an explicit "not measured" state, and no risk claim. It does not change what a scan writes: it reads a finished `*_galaxy_master.db` read-only.

## Engineering Summary
[Connectivity (API Surface)](08-14-api-exposure.md) measures what a file offers (export keywords against private ones). Reach measures what is used: the call graph records which function calls which, so counting distinct caller files and caller functions, plus a second hop, gives a unit people can reason about. Everything is computed after the scan from tables it already wrote.

## Purpose
To list the files the rest of the code depends on, report headers by include count, and say plainly which files the call graph cannot see.

## Problem Being Solved
Export keywords say little about use (a file can export many functions nobody calls), and for C-family code the ratio is computed on the wrong file (headers declare, source files define). The one use-based term in the Connectivity score, the popularity multiplier, is capped and enters a product.

## Design
1. **Caller counts (source files).** Per file: distinct other files that call a function it defines (`reach_files`), distinct caller functions (`caller_functions`), and callers of those callers (`one_hop_out`). A call from a file's top-level code counts as a caller file, not a caller function.
2. **Which edges count.** Only `fcall_data` rows with `kind = 'call'` that resolve to exactly one definition (`candidates` of 1 or null, destination known). Ties (no destination) and ambiguous edges (the resolver chose a file among several candidates) are not counted, and the report states how many. Their files are shown beside the count as `possible_caller_files`: files that may call the file through a tied call (`fcall_candidates`, #8161, one per platform variant in C) or an ambiguous one, and are not already counted. They are never added to the count by default; `--rank-with-possible` ranks the lists by counted plus possible callers. In a head-to-head against compiler-grade references (libclang, pyan3, the TypeScript checker, Go VTA, scip-java, rust-analyzer; 16 repositories in 7 languages) the possible callers raise recall in every language, but they cost precision outside C (TypeScript 91% to 41%, Java 82% to 67%) and the ranking moves both ways, which is why they are shown beside the count and not folded into it; in C they raise recall from 70% to 82% with no precision loss. Possible callers appear on source files; headers are counted by include.
3. **Headers use include counts.** The number of files whose `#include` names the header, resolved by path (a `"a/x.h"` include matches the header ending in `a/x.h`; a bare `"x.h"` prefers the includer's own folder, then the longest shared path), so same-named headers in different folders stay separate. This needs `--src` (the scanned tree); without it headers are reported as not measured.
4. **Not measured, with a reason.** A file with no functions, or a header without `--src`. These are never reported as zero.
5. **Role tag.** Source, tests and docs, CI configuration. Lists default to source; `--all-roles` includes the rest.
6. **Most-used public functions.** Public functions ranked by the number of other files that call them.
7. **Scope of a name (`--callee NAME`).** Who calls `NAME`, whether the repository defines it (from `fcall_data`) or not (from `fcall_external`, written by scans from the release that added that table). The scope of a rename or removal: files, calling functions, split by role. On curl, scanning the parent of the commit that replaced `free` with `curlx_free` (193cb00ce9, 471 files touched) and asking for `free` predicted 168 files; the commit changed `free(` calls in 161 files and 157 are in both lists (recall 0.98, precision 0.93). The misses are macro definitions; the extra files are mostly packaging code the commit did not touch.

## Pipeline Integration
- **Inputs:** `file_data`, `function_data` and `fcall_data` from the scan database (opened read-only); the source tree for include counts.
- **Outputs:** a text report, and with `--json` the full per-file result.
- **Dependencies:** [the call-graph builder](../../gitgalaxy/core/README.md); nothing is added to the scan itself.

## Tradeoffs
- Counts give up a cross-repository scale; read the lists within one repository. Reach grows with repository size.
- Leaving out ambiguous edges trades a few real callers for fewer guessed ones.

## Limitations
- **Counts are lower bounds.** Calls to names the scan cannot resolve (standard library, macros) are not recorded; in the exploratory tests the engine's callers were always real (precision 1.00) but about half complete.
- Header reach for languages without an include directive is not measured.
- In Go and Python the call graph matches by name, so same-named methods in different packages can be merged and counts over-state reach.
- Reach says nothing about quality or risk. Its relation to later fixes is small and descriptive: it adds +0.012 to +0.018 AUC to code size on three C projects.

## Performance Notes
No extra scan: counts come from rows already in the database, so a run takes a fraction of a second on a 1,100-file repository; include parsing is one pass over the C-family sources.

## Future Work
Persist include counts in the scan so header reach needs no second pass. (External callees are persisted by `fcall_external`; scoping a name needs a scan that wrote it.) Three views are prototypes in the research repository and not part of this command: stable foundations (high reach and no commit in a year), a migration-scope report for a planned rename, and the combination with recent activity.

## Related Components
- [Connectivity (API Surface)](08-14-api-exposure.md)
- [Chronometer](02-15-chronometer.md) (history, for the combined list)

## Evidence and Provenance
Exploratory, seven repositories (curl, libgit2, redis, libxml2, prometheus, sphinx, ripgrep), one snapshot each: per function, the engine's cross-file callers agree with a text search at Spearman +0.74 to +0.92; per file, caller files tracked a text-search reach at +0.63 to +0.91; for headers call-based reach does not work (-0.18 to +0.23 against include counts). temporal-crucible, branch `sensor-overhaul`, `docs/sensor-overhaul/sensors/reach.md` and `reach_validity_output.txt`. No registered test.
