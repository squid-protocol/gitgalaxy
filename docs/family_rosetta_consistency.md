# Cross-language consistency of the keyword families on keyword-rosetta (#8863, step 2)

keyword-rosetta writes the same probe program in 50 languages. A family that fires in most of the languages that have a rule for it and
reads 0 in a few has a gap in those few, with no parser oracle needed. `tests/tools/family_rosetta_consistency.py` builds the table;
this page is a dated snapshot of two runs (corpus `2e67433`, engine `719cd20d7b`). The corpus moves, so rerun the commands rather than
trusting the numbers after it does.

```
KEYWORD_ROSETTA_PATH=<checkout> python tests/tools/family_rosetta_consistency.py          # run 1: the blessed manifests
KEYWORD_ROSETTA_PATH=<checkout> python tests/tools/family_rosetta_consistency.py --live   # run 2: manifests plus a live count for unplanted families
```

## Reading

* **Run 1 (manifests, 30 planted families): one silent cell.** `dead_code` reads 0 in python, where 4 of the 5 languages that define it
  fire. No other planted family has a silent cell; the rest are clean, ledgered (`api` 21 cells, `args` 9), over the target (`api` 8, `func_start` 2) or have no consensus.
* **Run 2 (`--live`) counts the unplanted families from the corpus sources.** Its silent cells are marked `(reading)`: a raw count the
  detector's post-filter may remove, so they are leads, not defects, and `--check-floor` ignores them. The two largest:
  `panics_and_aborts` (21 languages read 0, 16 read above the target) and `structural_boundaries` (m4, scheme).
* **Spread, not silence:** `calls_out` (23 over, 17 under a target of 26) and `structural_boundaries` (23 over, 19 under a target of 18)
  disagree on the count in nearly every language. The probe plants one call shape and one boundary; the spread is a contract question,
  not a missing keyword.
* **Live vs manifest drift** (second run, last section): `abap` args, `c` safety, `go` globals, `hlasm` func_start, `java` io,
  `matlab` state_mutation and `yaml` args differ between the blessed manifest and a live count. The manifest count is used for judging.
* **Not judged:** the four `lit_*` families are not planted; families firing in under half of their languages are listed, not judged.

## Sibling gaps (no issues filed)

| member | status | why not here |
|---|---|---|
| `dead_code` python silent | open lead | a rule-contract audit of `dead_code`, with the matching keyword-rosetta plant |
| `panics_and_aborts` 21 silent readings | open lead | needs the live count compared with the post-filtered engine count per language |
| `calls_out`, `structural_boundaries` spread | open | contract audit (the tool's own sibling list) |
| no-consensus families (probe too thin) | open | keyword-rosetta SPEC plants for the unplanted families |
| CI `--check-floor` | owner decision | not wired |

## Run 1: manifests

Languages read: 50; corpus 2e67433.

| family | defined | fire | target | silent | over | under | ledgered | verdict |
|---|---|---|---|---|---|---|---|---|
| api | 50 | 47 | 12 | 0 | 8 | 0 | 21 | consensus |
| args | 49 | 49 | 13 | 0 | 0 | 0 | 9 | consensus |
| branch | 49 | 49 | 3 | 0 | 0 | 0 | 0 | consensus |
| class_start | 46 | 7 | 1 | 0 | 0 | 0 | 0 | no consensus |
| cleanup | 48 | 48 | 2 | 0 | 0 | 0 | 0 | consensus |
| dead_code | 5 | 4 | 1 | 1 | 0 | 0 | 0 | consensus |
| doc | 48 | 48 | 1 | 0 | 0 | 0 | 0 | consensus |
| encapsulation | 8 | 2 | 1 | 0 | 0 | 0 | 0 | no consensus |
| fragile_debt | 50 | 50 | 1 | 0 | 0 | 0 | 0 | consensus |
| func_start | 50 | 50 | 13 | 0 | 2 | 0 | 3 | consensus |
| globals | 48 | 48 | 2 | 0 | 0 | 0 | 0 | consensus |
| high_risk_execution | 49 | 49 | 3 | 0 | 0 | 0 | 1 | consensus |
| import | 50 | 50 | 3 | 0 | 0 | 0 | 1 | consensus |
| io | 48 | 48 | 3 | 0 | 0 | 0 | 0 | consensus |
| lit_code_blocks | 0 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| lit_diagrams | 0 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| lit_headers | 0 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| lit_links | 0 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| memory_alloc | 1 | 1 | 4 | 0 | 0 | 0 | 0 | consensus |
| ownership | 50 | 50 | 1 | 0 | 0 | 0 | 0 | consensus |
| panics_and_aborts | 2 | 2 | 1 | 0 | 1 | 0 | 0 | consensus |
| planned_debt | 50 | 50 | 1 | 0 | 0 | 0 | 0 | consensus |
| safety | 49 | 49 | 2 | 0 | 0 | 0 | 0 | consensus |
| safety_bypasses | 49 | 49 | 2 | 0 | 0 | 0 | 2 | consensus |
| spec_exposure | 5 | 5 | 1 | 0 | 0 | 0 | 0 | consensus |
| state_mutation | 47 | 47 | 2 | 0 | 0 | 0 | 3 | consensus |
| telemetry | 48 | 48 | 2 | 0 | 0 | 0 | 0 | consensus |
| test | 45 | 45 | 2 | 0 | 0 | 0 | 0 | consensus |
| thread_sleeps | 1 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| ui_framework | 1 | 1 | 28 | 0 | 0 | 0 | 0 | consensus |

## Silent cells (1): the language has a rule, most languages fire, this one reads 0

- `dead_code` (target 1, fires in 4 of 5): python

## Over the target

- `api` (target 12): abap=13, ada=13, bms=14, dart=13, hlasm=13, objective-c=13, perl=13, pli=13
- `func_start` (target 13): css=14, makefile=14
- `panics_and_aborts` (target 1): hlasm=2

## Under the target

None.

## Not judged

Contracted families the corpus does not plant (not testable here): `auth_middleware`, `bitwise_ops`, `calls_out`, `closures`, `comprehensions`, `concurrency`, `cryptography`, `debug_prints`, `decorators`, `dependency_injection`, `dl_frameworks`, `events`, `exfiltration_camouflage`, `explicit_casts`, `generics`, `hardcoded_secrets`, `hardware_bridge`, `immutability_locks`, `inline_asm`, `ipc_rpc_bridges`, `lazy_evaluation`, `listeners`, `llm_api`, `llm_orchestrator`, `llm_vector_store`, `macros`, `memory_scraping`, `ml_traditional`, `pointers`, `rce_funnel`, `reflection_metaprogramming`, `regex_execution`, `scientific`, `serialization_parsing`, `short_circuit`, `ssr_boundaries`, `structural_boundaries`, `sync_locks`, `system_config_mutation`, `test_skip`, `time_date_logic`, `vectorized_math`.
Families with no consensus (fire in under half of the languages that define them): `class_start` (7 of 46), `encapsulation` (2 of 8), `lit_code_blocks` (0 of 0), `lit_diagrams` (0 of 0), `lit_headers` (0 of 0), `lit_links` (0 of 0), `thread_sleeps` (0 of 1).
Corpus folders that are not a code language in the registry (skipped): markdown.

## Run 2: `--live`

Languages read: 50; corpus 2e67433.

| family | defined | fire | target | silent | over | under | ledgered | verdict |
|---|---|---|---|---|---|---|---|---|
| api | 50 | 47 | 12 | 0 | 8 | 0 | 21 | consensus |
| args | 49 | 49 | 13 | 0 | 0 | 0 | 9 | consensus |
| auth_middleware | 26 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| bitwise_ops | 41 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| branch | 49 | 49 | 3 | 0 | 0 | 0 | 0 | consensus |
| calls_out | 44 | 44 | 26 | 0 | 23 | 17 | 0 | consensus |
| class_start | 46 | 7 | 1 | 0 | 0 | 0 | 0 | no consensus |
| cleanup | 48 | 48 | 2 | 0 | 0 | 0 | 0 | consensus |
| closures | 26 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| comprehensions | 36 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| concurrency | 43 | 2 | 1 | 0 | 0 | 0 | 0 | no consensus |
| cryptography | 4 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| dead_code | 50 | 4 | 1 | 0 | 0 | 0 | 0 | no consensus |
| debug_prints | 46 | 5 | 2 | 0 | 0 | 0 | 0 | no consensus |
| decorators | 34 | 7 | 1 | 0 | 0 | 0 | 0 | no consensus |
| dependency_injection | 30 | 1 | 3 | 0 | 0 | 0 | 0 | no consensus |
| dl_frameworks | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| doc | 48 | 48 | 1 | 0 | 0 | 0 | 0 | consensus |
| encapsulation | 36 | 2 | 1 | 0 | 0 | 0 | 0 | no consensus |
| events | 44 | 2 | 1 | 0 | 0 | 0 | 0 | no consensus |
| exfiltration_camouflage | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| explicit_casts | 40 | 3 | 1 | 0 | 0 | 0 | 0 | no consensus |
| fragile_debt | 50 | 50 | 1 | 0 | 0 | 0 | 0 | consensus |
| func_start | 50 | 50 | 13 | 0 | 2 | 0 | 3 | consensus |
| generics | 32 | 1 | 1 | 0 | 0 | 0 | 0 | no consensus |
| globals | 48 | 48 | 2 | 0 | 0 | 0 | 0 | consensus |
| hardcoded_secrets | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| hardware_bridge | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| high_risk_execution | 49 | 49 | 3 | 0 | 0 | 0 | 1 | consensus |
| immutability_locks | 44 | 6 | 1 | 0 | 0 | 0 | 0 | no consensus |
| import | 50 | 50 | 3 | 0 | 0 | 0 | 1 | consensus |
| inline_asm | 10 | 1 | 1 | 0 | 0 | 0 | 0 | no consensus |
| io | 48 | 48 | 3 | 0 | 0 | 0 | 0 | consensus |
| ipc_rpc_bridges | 37 | 15 | 1 | 0 | 0 | 0 | 0 | no consensus |
| lazy_evaluation | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| listeners | 41 | 3 | 3 | 0 | 0 | 0 | 0 | no consensus |
| llm_api | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| llm_orchestrator | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| llm_vector_store | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| macros | 32 | 2 | 1 | 0 | 0 | 0 | 0 | no consensus |
| memory_alloc | 36 | 10 | 1 | 0 | 0 | 0 | 0 | no consensus |
| memory_scraping | 1 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| ml_traditional | 1 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| ownership | 50 | 50 | 1 | 0 | 0 | 0 | 0 | consensus |
| panics_and_aborts | 48 | 27 | 1 | 21 | 16 | 0 | 0 | consensus |
| planned_debt | 50 | 50 | 1 | 0 | 0 | 0 | 0 | consensus |
| pointers | 33 | 6 | 1 | 0 | 0 | 0 | 0 | no consensus |
| rce_funnel | 2 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| reflection_metaprogramming | 48 | 8 | 1 | 0 | 0 | 0 | 0 | no consensus |
| regex_execution | 33 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| safety | 49 | 49 | 2 | 0 | 0 | 0 | 0 | consensus |
| safety_bypasses | 49 | 49 | 2 | 0 | 0 | 0 | 2 | consensus |
| scientific | 46 | 1 | 2 | 0 | 0 | 0 | 0 | no consensus |
| serialization_parsing | 35 | 4 | 1 | 0 | 0 | 0 | 0 | no consensus |
| short_circuit | 34 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| spec_exposure | 50 | 5 | 1 | 0 | 0 | 0 | 0 | no consensus |
| ssr_boundaries | 32 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| state_mutation | 47 | 47 | 2 | 0 | 0 | 0 | 3 | consensus |
| structural_boundaries | 50 | 48 | 18 | 2 | 23 | 19 | 1 | consensus |
| sync_locks | 43 | 4 | 1 | 0 | 0 | 0 | 0 | no consensus |
| system_config_mutation | 1 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| telemetry | 48 | 48 | 2 | 0 | 0 | 0 | 0 | consensus |
| test | 45 | 45 | 2 | 0 | 0 | 0 | 0 | consensus |
| test_skip | 39 | 2 | 1 | 0 | 0 | 0 | 0 | no consensus |
| thread_sleeps | 45 | 1 | 1 | 0 | 0 | 0 | 0 | no consensus |
| time_date_logic | 37 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |
| ui_framework | 38 | 3 | 1 | 0 | 0 | 0 | 0 | no consensus |
| vectorized_math | 3 | 0 | 0 | 0 | 0 | 0 | 0 | no consensus |

## Silent cells (23): the language has a rule, most languages fire, this one reads 0

- `panics_and_aborts` (target 1, fires in 27 of 48): abap (reading), agc_assembly (reading), c (reading), cobol (reading), css (reading), db2_sql (reading), dockerfile (reading), embedded_python (reading), haskell (reading), html (reading), javascript (reading), m4 (reading), makefile (reading), matlab (reading), php (reading), powershell (reading), python (reading), shell (reading), solidity (reading), typescript (reading), yaml (reading)
- `structural_boundaries` (target 18, fires in 48 of 50): m4 (reading), scheme (reading)

## Over the target

- `api` (target 12): abap=13, ada=13, bms=14, dart=13, hlasm=13, objective-c=13, perl=13, pli=13
- `calls_out` (target 26): ada=31, apex=32, c=33, cpp=28, csharp=31, dart=29, go=33, haskell=28, javascript=27, livecode=60, lua=31, m4=49, matlab=32, perl=34, php=33, powershell=49, ruby=44, rust=29, scheme=67, shell=34, solidity=39, tcl=57, zig=32
- `func_start` (target 13): css=14, makefile=14
- `panics_and_aborts` (target 1): assembly=2, cpp=2, csharp=2, dart=3, go=3, groovy=2, hlasm=2, kotlin=15, livecode=2, lua=2, objective-c=3, perl=2, pli=2, rust=3, swift=2, yacc=3
- `structural_boundaries` (target 18): ada=41, agc_assembly=30, cpp=28, csharp=23, db2_sql=41, embedded_python=35, go=21, groovy=31, hlasm=28, javascript=29, kotlin=32, lua=33, perl=37, php=29, pli=32, python=31, rexx=24, rust=20, shell=22, solidity=45, swift=32, tcl=30, typescript=31

## Under the target

- `calls_out` (target 26): abap=3, agc_assembly=1, assembly=7, cobol=2, db2_sql=24, fortran=5, groovy=25, hlasm=3, java=24, jcl=13, kotlin=24, makefile=1, objective-c=13, pli=14, rexx=4, swift=25, yacc=10
- `structural_boundaries` (target 18): abap=15, apex=14, bms=5, c=14, cobol=15, css=16, dockerfile=3, haskell=12, html=10, jcl=14, livecode=9, makefile=1, matlab=16, objective-c=15, ruby=16, scala=3, sqlite=7, yacc=1, yaml=6

## Not judged

Contracted families the corpus does not plant (not testable here): `lit_code_blocks`, `lit_diagrams`, `lit_headers`, `lit_links`.
Families with no consensus (fire in under half of the languages that define them): `auth_middleware` (0 of 26), `bitwise_ops` (0 of 41), `class_start` (7 of 46), `closures` (0 of 26), `comprehensions` (0 of 36), `concurrency` (2 of 43), `cryptography` (0 of 4), `dead_code` (4 of 50), `debug_prints` (5 of 46), `decorators` (7 of 34), `dependency_injection` (1 of 30), `dl_frameworks` (0 of 3), `encapsulation` (2 of 36), `events` (2 of 44), `exfiltration_camouflage` (0 of 3), `explicit_casts` (3 of 40), `generics` (1 of 32), `hardcoded_secrets` (0 of 3), `hardware_bridge` (0 of 3), `immutability_locks` (6 of 44), `inline_asm` (1 of 10), `ipc_rpc_bridges` (15 of 37), `lazy_evaluation` (0 of 3), `listeners` (3 of 41), `llm_api` (0 of 3), `llm_orchestrator` (0 of 3), `llm_vector_store` (0 of 3), `macros` (2 of 32), `memory_alloc` (10 of 36), `memory_scraping` (0 of 1), `ml_traditional` (0 of 1), `pointers` (6 of 33), `rce_funnel` (0 of 2), `reflection_metaprogramming` (8 of 48), `regex_execution` (0 of 33), `scientific` (1 of 46), `serialization_parsing` (4 of 35), `short_circuit` (0 of 34), `spec_exposure` (5 of 50), `ssr_boundaries` (0 of 32), `sync_locks` (4 of 43), `system_config_mutation` (0 of 1), `test_skip` (2 of 39), `thread_sleeps` (1 of 45), `time_date_logic` (0 of 37), `ui_framework` (3 of 38), `vectorized_math` (0 of 3).

## Live vs manifest (manifest/live): the manifest count is used; the live count lacks a detector post-filter, or the manifest is stale

- `abap`: args=13/16
- `c`: safety=2/1
- `go`: globals=2/23
- `hlasm`: func_start=13/14
- `java`: io=3/0
- `matlab`: state_mutation=2/17
- `yaml`: args=13/67
