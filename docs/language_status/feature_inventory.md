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

Every category includes an explicit `unknown` bucket for constructs the parser refuses.

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
