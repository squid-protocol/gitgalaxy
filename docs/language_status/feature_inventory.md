---
description: "Documentation for the COBOL feature inventory extractor, which scans mainframe estates to catalog statements, CICS/SQL usage, data types, and compile options."
---

# Feature Inventory Extractor

The Readiness Scanner uses `feature_inventory.py` to extract a deterministic JSON inventory of COBOL features from an estate's codebase. It produces a detailed census of:
- **Statement Forms**: Base COBOL verbs (`PERFORM`, `MOVE`, `IF`, etc.)
- **Data Types**: Common usages and PICTURE characteristics (`COMP-1`, `COMP-2`, `COMP-3`, `P-SCALED`, `EDITED`, `NATIONAL`)
- **CICS Commands & Options**: CICS execution footprints (`SEND TEXT`, `READQ TS`) and their used options
- **SQL Forms**: Pre-compiler semantics (`DECLARE CURSOR`, `STATIC`, `DYNAMIC`)
- **Intrinsic Functions**: `FUNCTION CURRENT-DATE` and similar calls
- **Compile Options**: Semantic options resolved from JCL PARM and CBL/PROCESS cards
- **Copybook Resolution Gaps**: Explicit tracking of missing copybooks
- **Era tags** (#5117): per program, the CICS/COBOL era its source evidences (see below)

Every category includes an explicit `unknown` bucket for constructs the parser refuses.

## Era tags (#5117)
`tests/tools/era_tags.py` tags each program from its own text with an era 0-4 and lists the tells it used, so an estate
reads as "N programs show era-1 evidence" rather than a date. The inventory's `eras` section holds `programs` (per
program: `era`, `earliest`, `mixed`, `tells` with count and first line) and an estate `summary` (programs per era,
mixed, programs per tell).

| Era | Tells |
|---|---|
| 0 | `DFHxx TYPE=` macro calls (assembler text), `DFHCSADS` / `DFHTCADS` |
| 1 | BLL cells, `SERVICE RELOAD`, `HANDLE CONDITION/AID/ABEND`, `CBLTDLI` / `EXEC DLI`, `CBL LANGLVL(1)` |
| 2 | `ADDRESS OF`, `SET ADDRESS`, `RESP/RESP2`, `EXEC SQL`, `LINK ... SYSID` (DPL), `CMPR2`, `LANGLVL(2)` |
| 3 | `CALL 'MQxxx'`, EXCI (`DFHXCIS`), 3270 bridge (`DFHBRxxx`), LE callable services (`CALL 'CEExxxx'`) |
| 4 | channels / containers, `EXEC CICS WEB` / SOAP, `JSON` / `XML PARSE|GENERATE`, `RUN TRANSID` / `FETCH`, named counters, `ARITH(EXTEND)` |

A program's `era` is the latest era a tell reaches. Most tells are floors (RESP is written in every later era), so
they only raise the era; the period-bound ones (macros, BLL, HANDLE CONDITION, DL/I, CMPR2, LANGLVL) set `earliest`,
and a program whose period-bound tell is older than its era is `mixed` (layered code). `era: null` means no tell.
Comments, string literals and columns 1-6 / 73-80 are not read; a program the parser refuses is still tagged (the tag
reads the raw text); a tell inside a copybook is not seen. This only detects: parsing the macro tables (#5120) and
refusing macro-level programs (#5121) are separate. The support matrix prints the distribution and the mixed programs
per estate.

## How to Run
Run against a single local estate directory to print the inventory:
```bash
python tests/tools/feature_inventory.py /path/to/estate [--out output.json]
```

Or regenerate the baseline fixtures for all burned corpora:
```bash
python tests/tools/feature_inventory.py --all-burned --write
```
Run `--all-burned --check` to exit 1 if any committed fixture is stale.

## The Schema
The inventory conforms to a JSON schema (`tests/tools/feature_inventory.schema.json`). Each feature key contains its occurrences (`count`) and an alphabetically sorted array of relative program paths that use it (`programs`).

## Known Limits
- Unparsed features, such as syntactically broken CICS statements or unrecognized layout values, correctly bump the corresponding `unknown` bucket but are not structurally classified.
- SQL forms strictly partition into `STATIC` vs `DYNAMIC` and cursor presence; deep AST SQL parsing is deferred to dedicated tools.
- National types that cause the detector to abort the unit are recorded as `unknown` statement/data buckets rather than a discrete `NATIONAL` feature count, unless successfully captured by the layout engine.

## Differences with cics_census.py
There is a minor discrepancy in CICS command totals (e.g., 233 vs 240 for CardDemo) between `feature_inventory.py` and `cics_census.py`. This occurs because `feature_inventory.py` relies on deep AST parsing (which resolves copybooks and drops syntactically invalid commands into the unknown bucket) and uses a raw regex fallback for fully unparsable programs, whereas `cics_census.py` strictly uses a regex over `fixed_format_text` (which strips comments and handles continuations) for all programs.

## Support matrix (#4724)
`tests/tools/support_matrix.py` joins each burned estate's inventory fixture with its evidence report
(`<estate>/report.json` of the evidence report published on `generated`: each program's level, proving case, and translate-only
refusal or holes), the rule catalogue (`docs/language_status/cobolrt_rules.json`, #4711; "not yet catalogued" while it
is absent) and `docs/language_status/refusal_map.json` (each refusal or hole text: its issue, its agreed refusal family
in [definition_of_done.md](definition_of_done.md), or the IBM product library a missing copybook belongs to). It reads
committed files only: no corpus, no scan.
```bash
python tests/tools/support_matrix.py [ESTATE ...] [--json] [--catalogue PATH] [--out FILE]
```
Each feature is **supported and proven** (a program using it is at L2 or above), **supported, unproven** (translated,
no refusal names it, no proof), **refused by name**, or **unknown / never seen** (only programs refused whole use it),
with the conditions of "supported" (charter section 5) it does not meet yet. Per estate it also lists the refusals
with their owners, the missing system copybooks (a configuration fix: name SCSQCOBC / SCEESAMP), the runtime APIs a
program calls that are not modelled (MQ: translates, not provable), and what is unknown, for triage.
`tests/cobol_mainframe/test_support_matrix.py` fails when a refusal or hole of a committed report matches no entry of
`refusal_map.json` (or more than one): a new one after an evidence refresh is added there with its owner.
