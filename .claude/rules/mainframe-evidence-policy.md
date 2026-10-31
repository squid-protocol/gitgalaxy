---
description: "Owner decisions on mainframe evidence: how to report proof, which estates may be read, callee holes, level estates, system copybooks"
globs: "gitgalaxy/tools/cobol_to_java/**, tests/tools/*evidence*, tests/tools/det_port*, docs/language_status/**"
---
# Mainframe Evidence Policy (owner decisions)

These are settled. Follow them; do not re-ask.

### 1. Evidence levels, never "proven / not proven" (owner, 2026-10-07)
Report the ladder with counts: translated (whole / holes / refused, with reasons), executed-equivalent (cases,
scenarios, diffs), paragraph % and branch %, the assumptions relied on, and the residual risk. The oracle is
GnuCOBOL plus our stub, not z/OS.

### 2. Burned estates only for case and proof work (owner, 2026-10-09)
The burned (development) estates are `estate4_draw.BURNED_NAMES` in `tests/tools/estate4_draw.py`: CardDemo, CBSA,
GenApp, zECS, DBB MortgageApplication, cicsdev async credit-card.
* Never burn, pin or write cases for a non-burned census repo: those keep their first-contact numbers.
* A program that is whole only in a non-burned repo is out of scope: list it, don't ask.
* Before planning a "state it per case" box, grep the burned corpora (`.mainframe_corpora`) for the construct: if no
  burned program reads it, there is nothing to prove (#5221).
* Translation rankings (`cics_census.py blockers`, the blocker-slice skill's "non-burned first") still count
  non-burned programs automatically. Ranking by them is fine; reading, porting or writing cases for them is not.

### 3. The blind estate
Census and blind-estate candidate repos are counted by tools only: never open or read their code. Never suggest a
candidate without checking the ineligible list (`INELIGIBLE_LIST` in `tests/tools/estate4_draw.py`; the draw rules
and result are `docs/language_status/estate4_candidates.md` / `.json`).

### 4. Callee holes (owner, 2026-10-11, #4803)
A program is not proven while any program it CALLs or LINKs to (transitively) has holes, even unreached ones.
Record its cases at the lower level, with the reason.

### 5. Level estates first (owner, 2026-10-11)
For a new estate region (utilities / JCL #4890-#4891, MQ #4892, IMS #4893, VSAM #4894) build the level
estate-crucible before support lands. Its first run is the first-time number, measured once; afterwards it is
development data.

### 6. System copybooks (owner, 2026-10-11)
Never ship IBM's copybooks. A stand-in written from public docs, recorded as a register assumption, is allowed only
where GitGalaxy models the runtime behind it (LE `CEEIGZCT`: yes, #4884). MQ copybooks stay refused until an MQ
model exists (#4514). The same holds for other vendors' copybooks.

### 7. Undefined by IBM (owner, 2026-10-29, #6072)
An outcome reachable only through an out-of-range subscript or reference modification, where IBM (no SSRANGE) leaves the
result undefined and GnuCOBOL refuses (register X8, `bounds_refused`), is its own class: **undefined by IBM**, family `U`
in `tests/equivalence/infeasible_outcomes/<case>.json`.
* **Extended (owner, 2026-10-31, #6839 row J):** the same class holds for an outcome reachable only through non-digit data
  in a numeric USAGE DISPLAY item (IBM documents no result; GnuCOBOL reads `ttl=abc` as zeros, so NUMERIC passes where
  z/OS would fail it). Register C11 records the wider ruling.
* Report it by name with counts (the evidence report's "undefined by IBM" line). Never as proven, never as infeasible: an
  input does reach it, and IBM does not say what happens.
* The branch bar is taken net of it, as of stated infeasible outcomes; a proof that reaches one still refutes the entry.
* First members: BNK1CAC `ED010` 611:true, 637:true, 637:false, 717:true; ZECS001 `1310-TTL` 704:false (non-digit). The harness slice that would judge them is queued
  in #6072 (Remaining slices).

