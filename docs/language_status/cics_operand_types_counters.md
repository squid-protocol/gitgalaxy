# EXEC CICS named-counter operand types: det's data-area / data-value audit (#8058)

Slice of the #8058 audit for the named-counter commands (`det/cics_counters.py`); the main table is
[cics_operand_types.md](cics_operand_types.md). IBM topics (CICS TS 6.x, read 2026-11-09):
`summary-get-counter-get-dcounter`, `summary-update-counter-update-dcounter`, `summary-define-counter-define-dcounter`,
`summary-query-counter-query-dcounter`, `summary-rewind-counter-rewind-dcounter`, `summary-delete-counter-delete-dcounter`.
A data-area is a COBOL data name only; a data-value may also be a constant ("EXEC CICS command argument values").
Burned programs that use these commands: CBSA (named counters) and zECS ZECS001 (`GET DCOUNTER`, #4770).

## Options by command

Types are from IBM's syntax diagram; where a DCOUNTER diagram and its option heading disagree, both are shown.

| Command | Option | IBM type (COUNTER / DCOUNTER) | det path |
|---|---|---|---|
| all six | `COUNTER`, `DCOUNTER`, `POOL` | name (16 / 8 bytes, space padded) | `name` (a literal or a data name) |
| GET | `VALUE` | data-area / data-area (receiver) | `_cstore` -> `ref`: a literal is refused |
| GET | `INCREMENT`, `COMPAREMIN`, `COMPAREMAX` | data-value / data-area (heading: data-value) | `_clong` / `long_`: literal or data name |
| UPDATE | `VALUE` | data-value / data-area (heading: data-value) | `_clong`: literal or data name |
| UPDATE | `COMPAREMIN`, `COMPAREMAX` | data-value / data-area (heading: data-value) | refused by name: not modelled (IBM leaves the tested value open) |
| DEFINE | `VALUE`, `MINIMUM` | data-value / data-value | `_cint` / `_clong`: literal or data name |
| DEFINE | `MAXIMUM` | data-value / data-area (heading: data-value) | `_cint` / `_clong`: literal or data name |
| QUERY | `VALUE`, `MINIMUM`, `MAXIMUM` | data-area / data-area (receivers) | `_cstore` -> `ref`: a literal is refused |
| REWIND | `INCREMENT` | data-value / data-area (heading: data-value) | `_clong`: literal or data name |
| DELETE | none beyond the name | | |

`NOSUSPEND`, `REDUCE` and `WRAP` take no argument. A raw (PIC X / group) area in a binary option is read as IBM's
fullword (COUNTER) or unsigned doubleword (DCOUNTER) bytes (#7434).

Result: no data-value option is read through the strict data-area path, and no receiver accepts a constant, so this family
needs no translator change. `tests/cobol_mainframe/test_det_cics_counter_operands_8058.py` pins both sides for COUNTER and DCOUNTER.

## Sibling gaps

- **DCOUNTER `INCREMENT`, `COMPAREMIN`, `COMPAREMAX`, UPDATE `VALUE`, DEFINE `MAXIMUM`, REWIND `INCREMENT`:** the diagram says
  data-area, the heading data-value, IBM contradicts itself. det accepts a constant (the looser reading); tightening could
  change a burned port, so it waits for an owner ruling. No burned program passes a constant there (zECS passes data names).
- **UPDATE `COMPAREMIN` / `COMPAREMAX`:** not modelled (a modelling refusal, not a type one).
