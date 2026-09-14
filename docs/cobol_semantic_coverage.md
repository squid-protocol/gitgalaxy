# COBOL/JCL semantic-coverage assessment (#2990)

An audit of four new CICS sample repos in `data/corpus_cobol/` found that every `EXEC CICS`/`EXEC SQL`
line looks "covered" because `reflection_metaprogramming`'s bare catch-all fires on all of them, but
seven verb families carried no *semantic* signal — most visibly the CICS Async API (`RUN TRANSID` /
`FETCH CHILD|ANY`), so a modern parallel CICS application scored `arch_concurrency = 0`. This document
is the systematic pass the issue asked for instead of seven one-off regex additions: every CICS/SQL/DLI
command and native-COBOL idiom actually observed in the corpus, mapped to its owning rule or recorded as
deliberately unowned, with the one-line reason in each case. It also covers JCL, per the issue's request
for a sibling pass.

## Method

`tests/tools/embedded_verb_coverage.py` (committed as the issue's reusable harness) parses every
`EXEC CICS|SQL|DLI ... END-EXEC` block (COBOL) or every JCL `//` statement/operand (JCL) out of the
corpus's *code stream* (comments already stripped by `Prism`), normalizes each to a canonical verb name,
and runs every non-blanket rule in the language's registry against it. A hand-maintained `EXPECTED_COBOL`
/ `EXPECTED_JCL` table records, for every verb the census actually finds, either:

- **owned** — the rule(s) that fire at ≥90% share (or a documented, lower `min_share` for a handful of
  legitimately coarse statement-class buckets — see below), with a reason;
- **blanket-only** — no non-blanket rule fires, and that is the *intended* semantic owner (an ambient
  introspection construct with no cross-language equivalent);
- **none** — deliberately unowned, with a reason;
- **GAP** or **MISMATCH** — a verb with real hits and no matching record, or a record that disagrees
  with what the rules actually do. `--check` exits 1 on either; that is the issue's acceptance criterion,
  runnable in CI.

Run it yourself: `python tests/tools/embedded_verb_coverage.py cobol --check --all` (add
`--extra <dir>...` to widen the census to repos not yet in `language-crucible`; `--markdown <path>` to
regenerate the tables below). It is a sibling of `tests/tools/rule_probe.py` and reuses its corpus-file
walker and stream helpers.

**Corpus used**: `language-crucible` v1.2.0 (591 real-world COBOL files, 195 JCL files) plus, for the
CICS Async API specifically, a scratch clone of the three `cicsdev` sample repos the issue's four-repo
audit named (`cics-async-api-credit-card-application-example`, `cics-async-fetch-variation-example`,
`cics-event-consumer`; Apache-2.0) — none of which is in `language-crucible` yet (only
`aws-mainframe-modernization-carddemo` is). See Follow-up #1: they should be added to the pinned corpus
in its own release so this table's async-API rows stay backed by the committed corpus, not a scratch
clone. `keyword-rosetta`'s `data/cobol`/`data/jcl` plants carry none of the newly-owned tokens, so no
corpus cell moves and no `keyword-rosetta` PR accompanies this one.

## Accepted duals

A few rows are owned by **two** rules on purpose, following the engine's existing precedent
(`test_cobol_intentional_double_classification_sweep`, e.g. `EXEC CICS DELAY` → concurrency +
thread_sleeps):

| verb | duals | why |
|---|---|---|
| `RUN TRANSID` | concurrency + ipc_rpc_bridges | spawns a child task (async) that also crosses a program boundary |
| `IF/EVALUATE SQLCODE` | branch + safety | the token IS a decision (branch) that tests a command's outcome (safety) — definitional |
| `DELETE COUNTER` | io + cleanup | boundary operation that also removes external state |
| `ENDBR` | io + cleanup | releases a browse cursor — the `EXEC SQL CLOSE` (cursor) shape |
| `SUSPEND` | concurrency + thread_sleeps | yields the task (async) by blocking it |
| `CEE3ABD` (`CALL`) | panics_and_aborts + ipc_rpc_bridges | the LE abend service, called like any program |

`HANDLE CONDITION` **moved out of** `events` (its declared contract excludes the receiving side) **and
into** `safety` (the stated #2869 contract's "installed failure handler"). `FREE CHILD` moved the
opposite way from what the bare-verb regex used to imply: it releases an async token, so it is
`cleanup`'s, not `memory_alloc`'s (the bare-verb `FREE` rule now excludes it explicitly).

## Corrections found by the census (not additions)

Three existing patterns mis-attributed real corpus text before this pass:

1. `EXEC CICS ABEND ... CANCEL` / `HANDLE ABEND CANCEL` / `EXEC CICS CANCEL REQID(...)` fired
   `high_risk_execution` via the bare COBOL `CANCEL` verb — 31% of the crucible's ABEND blocks read as a
   dangerous program unload for terminating abnormally instead. `high_risk_execution`'s `CANCEL`
   alternative now requires a program-name operand and excludes the CICS option/interval-control forms.
2. `EXEC CICS START TRANSID(...)` fired `io` via the bare file-positioning `START` verb whenever CICS and
   START were separated by more than one space (real shape, `cics-genapp/lgwebst5.cbl`) — a fixed-width
   lookbehind alone can't see a variable-width gap. Backed by a lookahead on the CICS-only operand words
   (`TRANSID`/`BREXIT`/`CHANNEL`/`AFTER`) that holds regardless of spacing.
3. `EXEC CICS FREE CHILD(...)` fired `memory_alloc` via the bare `FREE` verb — releasing an async child's
   token is `cleanup`'s (see the dual table above), not storage deallocation.

## CICS / SQL / DLI / native-COBOL coverage table

Generated by `embedded_verb_coverage.py cobol --check --all --extra <the three cicsdev repos> --markdown`.
`n` = occurrences across `language-crucible` + `keyword-rosetta` + the three extra repos; `files` =
distinct files. Sorted by `n`, descending.

### cobol

| verb | n | files | verdict | owner rule(s) | reason |
|---|---|---|---|---|---|
| `NATIVE:SORT` | 435 | 24 | none | — | a file-sort utility statement; no cross-language rule owns 'sort a dataset'. The io/branch noise below 90% share is from unrelated tokens (KEY, GIVING clauses) sharing SORT's captured line fragment, not SORT itself. |
| `NATIVE:DFHRESP(` | 398 | 52 | owned | branch, safety | #2990: `DFHRESP(` is the mainframe try/catch's value-level check (safety). branch also fires on 95% of real occurrences because the check is almost always written as an IF/EVALUATE condition -- an incidental corollary of the corpus's usage, not a design requirement of DFHRESP( itself. |
| `CICS:ASSIGN` | 266 | 31 | blanket-only | blanket | introspection of the task/terminal/system environment (APPLID, SYSID, ABCODE, ...); no cross-language rule owns 'read an ambient runtime attribute', and reflection_metaprogramming's bare EXEC CICS catch-all is the only signal it needs -- a dedicated rule would duplicate the blanket for a low-value, CICS-only construct. |
| `CICS:LINK` | 245 | 53 | owned | ipc_rpc_bridges | pre-#2990, unchanged: synchronous program-to-program call across a boundary. |
| `CICS:RETURN` | 199 | 97 | owned | ipc_rpc_bridges | pre-#2990, unchanged: returns control, optionally to another transaction. |
| `NATIVE:IF/EVALUATE SQLCODE` | 117 | 23 | owned | branch, safety | #2990: by construction this token IS an IF/EVALUATE (branch) testing SQLCODE (safety's value-level check) -- the dual is definitional. |
| `NATIVE:SEARCH` | 104 | 13 | none | — | a table-search statement (SEARCH / SEARCH ALL); no cross-language rule owns linear/binary table search. The branch/api/safety_bypasses noise below 90% share is from a same-line WHEN/AT END/INVALID KEY clause, not SEARCH itself. |
| `CICS:ABEND` | 91 | 47 | owned | panics_and_aborts | pre-#2990, unchanged: terminates the task abnormally. |
| `CICS:SEND MAP` | 91 | 31 | owned | ui_framework | pre-#2990, unchanged: formatted 3270 screen output. |
| `NATIVE:FUNCTION TRIM` | 88 | 8 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `NATIVE:FUNCTION UPPER-CASE` | 70 | 8 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `NATIVE:FILE STATUS clause` | 68 | 27 | none | — | a data-item declaration naming the field a READ/WRITE populates with its status code, not a call or check itself; the field name is user-chosen so no keyword anchors it. The debug_prints noise (23%) is files whose status field happens to be tested near a DISPLAY, not a property of the clause. |
| `CICS:ASKTIME` | 60 | 51 | owned | time_date_logic | #2990: reads the current time -- a clock call, no owner before this. |
| `CICS:FORMATTIME` | 59 | 51 | owned | time_date_logic | #2990: formats a time value -- same clock/calendar family. |
| `NATIVE:FUNCTION RANDOM` | 53 | 11 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `SQL:INCLUDE` | 53 | 23 | owned | io, ipc_rpc_bridges | pre-#2990 base (bare EXEC SQL alternative). The `import` rule fires on ~89% of these blocks (it names a real copybook, e.g. SQLCA/ACCDB2) but only when INCLUDE starts its own physical line -- a pre-existing, formatting-dependent positional dual, out of #2990's scope to make deterministic. |
| `NATIVE:FUNCTION NUMVAL` | 39 | 10 | owned | explicit_casts | #2990: string-to-numeric conversion. |
| `CICS:DEFINE COUNTER` | 37 | 1 | owned | io | #2990: creates a named counter in the coupling facility -- an external, shared store. |
| `CICS:DELETE COUNTER` | 37 | 1 | owned | cleanup, io | #2990: removes a named counter -- boundary + release of external state. |
| `CICS:PUT CONTAINER` | 36 | 23 | owned | ipc_rpc_bridges, state_mutation | pre-#2990 dual, unchanged: writes state that outlives the program AND hands it to another one. |
| `CICS:QUERY COUNTER` | 36 | 1 | owned | io | #2990: reads a named counter's value from the coupling facility. |
| `CICS:RECEIVE MAP` | 35 | 31 | owned | listeners | pre-#2990, unchanged: registration to receive formatted terminal input. |
| `NATIVE:FUNCTION CURRENT-DATE` | 35 | 26 | owned | time_date_logic | #2990: a date/time intrinsic, widened alongside the existing ACCEPT FROM DATE/TIME/DAY forms. |
| `NATIVE:FUNCTION INTEGER` | 35 | 5 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION MOD` | 33 | 4 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `CICS:READ` | 32 | 18 | owned | io | pre-#2990, unchanged: VSAM/file read. |
| `CICS:GET CONTAINER` | 31 | 19 | owned | ipc_rpc_bridges | pre-#2990, unchanged: reads a container -- the bridge without the mutation (GET CONTAINER's asymmetry with PUT is deliberate). |
| `NATIVE:FUNCTION LENGTH` | 31 | 7 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `NATIVE:CALL '<ordinary program>'` | 30 | 9 | owned | ipc_rpc_bridges | pre-#2990, unchanged: an ordinary application CALL. `args` fires only when the call happens to pass a USING list (60% of the corpus's calls do) -- a property of the individual call site, not of 'calling a program' in general, so it is not required here. |
| `CICS:SEND TEXT` | 28 | 25 | owned | ui_framework | #2990: bare terminal text output -- widened from SEND MAP only. |
| `CICS:SYNCPOINT ROLLBACK` | 27 | 12 | owned | safety | #2990: backs out the current unit of work -- same transactional-guard family. |
| `NATIVE:FUNCTION INTEGER-PART` | 27 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `CICS:DELAY` | 26 | 18 | owned | concurrency, thread_sleeps | pre-#2990 dual, unchanged: a forced wait (async primitive) that also blocks the task (thread_sleeps). |
| `CICS:XCTL` | 26 | 18 | owned | ipc_rpc_bridges | pre-#2990, unchanged: transfers control to another program. |
| `NATIVE:FUNCTION REM` | 24 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `SQL:SELECT` | 24 | 12 | owned | io, ipc_rpc_bridges | pre-#2990, unchanged. |
| `NATIVE:FUNCTION MEAN` | 22 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION REVERSE` | 22 | 7 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `NATIVE:FUNCTION STANDARD-DEVIATION` | 22 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION MEDIAN` | 21 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION MIDRANGE` | 21 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION ORD-MIN` | 21 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION VARIANCE` | 21 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION ORD-MAX` | 20 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION SUM` | 20 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `SQL:INSERT` | 20 | 11 | owned | io, ipc_rpc_bridges | pre-#2990, unchanged. |
| `NATIVE:FUNCTION INTEGER-OF-DATE` | 19 | 7 | owned | time_date_logic | #2990: a date/time intrinsic, widened alongside the existing ACCEPT FROM DATE/TIME/DAY forms. |
| `NATIVE:FUNCTION RANGE` | 19 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `SQL:DECLARE` | 19 | 13 | owned | io, ipc_rpc_bridges | pre-#2990, unchanged: declares a cursor. |
| `NATIVE:FUNCTION ANNUITY` | 18 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION LOWER-CASE` | 18 | 3 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `CICS:HANDLE ABEND` | 17 | 11 | owned | safety | #2990: installs an abend handler -- the stated #2869 sentence's 'installed failure handler'; moved from no owner. |
| `CICS:WRITEQ TS` | 17 | 6 | owned | io | pre-#2990, unchanged. |
| `NATIVE:FUNCTION DATE-OF-INTEGER` | 16 | 4 | owned | time_date_logic | #2990: a date/time intrinsic, widened alongside the existing ACCEPT FROM DATE/TIME/DAY forms. |
| `NATIVE:FUNCTION NUMVAL-C` | 15 | 4 | owned | explicit_casts | #2990: string-to-numeric conversion (currency-edited). |
| `NATIVE:FUNCTION ORD` | 15 | 3 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `SQL:FETCH` | 15 | 7 | owned | io, ipc_rpc_bridges | pre-#2990, unchanged: reads through a cursor. |
| `NATIVE:SIGNON` | 14 | 3 | none | — | CICS terminal signon; no base-schema rule owns authentication (see the filed follow-up on cobol's auth surface -- SIGNON/SIGNOFF/VERIFY PASSWORD/QUERY SECURITY/EXEC SQL GRANT/REVOKE all land here). |
| `SQL:UPDATE` | 14 | 7 | owned | io, ipc_rpc_bridges, state_mutation | pre-#2990, unchanged: an UPDATE ... SET is both a boundary and a write. |
| `NATIVE:FUNCTION FACTORIAL` | 13 | 2 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `CICS:RUN TRANSID` | 12 | 4 | owned | concurrency, ipc_rpc_bridges | #2990: spawns a child task -- the async spawn half of the Async API; also hands work to another transaction (ipc). |
| `NATIVE:NOHANDLE` | 12 | 8 | owned | safety_bypasses | #2990: switches CICS exception handling off for one command -- an error swallowed on purpose. |
| `SQL:CLOSE` | 12 | 8 | owned | cleanup, io, ipc_rpc_bridges | pre-#2990, unchanged: releases a cursor. |
| `CICS:REWRITE` | 11 | 8 | owned | io | pre-#2990, unchanged: VSAM/file update. |
| `NATIVE:FUNCTION DAY-OF-INTEGER` | 11 | 2 | owned | time_date_logic | #2990: a date/time intrinsic, widened alongside the existing ACCEPT FROM DATE/TIME/DAY forms. |
| `NATIVE:FUNCTION INTEGER-OF-DAY` | 11 | 2 | owned | time_date_logic | #2990: a date/time intrinsic, widened alongside the existing ACCEPT FROM DATE/TIME/DAY forms. |
| `SQL:OPEN` | 11 | 8 | owned | io, ipc_rpc_bridges | pre-#2990, unchanged: opens a cursor. |
| `NATIVE:FUNCTION CHAR` | 10 | 2 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `CICS:ENDBR` | 8 | 6 | owned | cleanup, io | #2990: releases a browse cursor -- the `EXEC SQL CLOSE` (cursor) shape, io + cleanup. |
| `CICS:READPREV` | 8 | 6 | owned | io | #2990: advances a browse cursor backward. |
| `CICS:SEND CONTROL` | 8 | 8 | owned | ui_framework | #2990: terminal control (cursor/erase) output -- same widening. |
| `CICS:STARTBR` | 8 | 6 | owned | io | #2990: opens a VSAM browse cursor -- a boundary operation, same family as the bare file verbs. |
| `CICS:WRITE` | 8 | 8 | owned | io | pre-#2990, unchanged: VSAM/file write. |
| `NATIVE:CALL 'CEE3ABD'` | 8 | 8 | owned | ipc_rpc_bridges, panics_and_aborts | #2990: the Language Environment abend service -- the batch sibling of EXEC CICS ABEND. ipc_rpc_bridges already owns every CALL (unchanged). |
| `CICS:BIF DEEDIT` | 7 | 5 | owned | explicit_casts | #2990: de-edits a numeric field back to a number -- a conversion call. |
| `CICS:FETCH CHILD` | 7 | 2 | owned | concurrency | #2990: joins a child task spawned by RUN TRANSID -- the async join half. |
| `CICS:READQ TS` | 7 | 4 | owned | io | pre-#2990, unchanged. |
| `CICS:SET TERMINAL` | 7 | 2 | owned | state_mutation | pre-#2990, unchanged: bare SET already fires state_mutation -- an SPI attribute WRITE is a real mutation, unlike the read-only INQUIRE/ASSIGN family. |
| `CICS:DELETEQ TS` | 6 | 2 | owned | io | pre-#2990, unchanged. |
| `CICS:HANDLE CONDITION` | 6 | 6 | owned | safety | #2990: installs a condition handler -- moved OUT of `events` (the declared row excludes the receiving side) and into `safety` per the stated #2869 contract. |
| `CICS:RECEIVE` | 6 | 6 | owned | listeners | pre-#2990, unchanged: registration to receive unformatted terminal input. |
| `NATIVE:FUNCTION TEST-NUMVAL-C` | 6 | 1 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `SQL:DELETE` | 6 | 4 | owned | cleanup, io, ipc_rpc_bridges | pre-#2990, unchanged. |
| `CICS:HANDLE AID` | 5 | 5 | owned | listeners | #2990: registers a handler for a terminal attention key -- a registration to receive, listeners' contract. |
| `CICS:DELETE` | 4 | 3 | owned | cleanup, io | pre-#2990, unchanged: removes a record from an external store -- io boundary and a release of that state. |
| `CICS:DEQ` | 4 | 4 | owned | concurrency | pre-#2990, unchanged: releases the ENQ lock -- task coordination. |
| `CICS:ENQ` | 4 | 4 | owned | concurrency, sync_locks | pre-#2990 dual, unchanged: task coordination + the CICS lock primitive. |
| `CICS:FETCH ANY` | 4 | 2 | owned | concurrency | #2990: joins whichever child completes first -- same async join family as FETCH CHILD. |
| `CICS:INQUIRE TERMINAL` | 4 | 2 | blanket-only | blanket | same SPI-introspection reasoning as ASSIGN -- reads a terminal's attributes. |
| `CICS:READNEXT` | 4 | 3 | owned | io | #2990: advances a browse cursor forward. |
| `CICS:SEND` | 4 | 4 | owned | safety_bypasses, ui_framework | #2990: bare SEND FROM(...) writes directly to the terminal with no map. The crucible's only 4 occurrences all carry NOHANDLE (real, deliberate error-suppression dual on this idiom -- not asserted as a general SEND property). |
| `NATIVE:FUNCTION PIC` | 4 | 4 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `NATIVE:MERGE` | 4 | 1 | none | — | a file-merge utility statement, same family as SORT; no cross-language owner. |
| `NATIVE:CALL 'DSNTIAR'` | 3 | 3 | owned | args, ipc_rpc_bridges, telemetry | #2990: formats a Db2 diagnostic message (telemetry, the CEEMOUT class) -- its calling convention always passes the SQLCA and an output buffer, so args is a genuine property of this specific service call, not incidental. |
| `NATIVE:FUNCTION MAX` | 3 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION MIN` | 3 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION WHEN-COMPILED` | 3 | 2 | owned | branch, time_date_logic | #2990 dual: WHEN-COMPILED is time's, and every real occurrence is inside an IF/EVALUATE (branch's decision) -- an incidental corollary of the corpus's own usage, not a design requirement. |
| `SQL:COMMIT` | 3 | 1 | owned | io, ipc_rpc_bridges, safety | #2990: added `safety` -- unit-of-work control, the same transactional guard as SYNCPOINT/sqlite's COMMIT. |
| `CICS:GET COUNTER` | 2 | 2 | owned | io | #2990: reads and increments a named counter -- same external-store boundary. |
| `CICS:IGNORE CONDITION` | 2 | 1 | owned | safety_bypasses, test_skip | pre-#2990 dual, unchanged: IGNORE CONDITION suppresses a handler (safety_bypasses); the bare word IGNORE is also test_skip's keyword. |
| `CICS:SYNCPOINT` | 2 | 2 | owned | safety | #2990: commits the current unit of work -- the transactional guard sqlite.py already counts as safety. |
| `CICS:WRITEQ TD` | 2 | 2 | owned | io, telemetry | pre-#2990 dual, unchanged: a transient-data write is a real io boundary AND the CICS journalling idiom. |
| `NATIVE:ACCEPT FROM (env/arg)` | 2 | 1 | none | — | reads a command-line argument or environment variable; distinct from python counting no `input()`/argv-read as io either -- kept consistent with that cross-language precedent rather than adding a COBOL-only exception. |
| `NATIVE:FUNCTION ACOS` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION ASIN` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION ATAN` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION COS` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION FUNC1` | 2 | 2 | none | — | a user-defined FUNCTION-ID (COBOL 2002+ allows programmer-defined intrinsics); not a library call this table can classify by name. |
| `NATIVE:FUNCTION LOG` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION LOG10` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION PRESENT-VALUE` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION SIN` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION SQRT` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION TAN` | 2 | 1 | owned | scientific | #2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set. |
| `NATIVE:FUNCTION TEST-NUMVAL` | 2 | 1 | none | — | a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap. |
| `NATIVE:INVOKE` | 2 | 1 | none | — | invokes an OO-COBOL method; the crucible carries only 2 occurrences and no rule owns generic method invocation for this registry. |
| `SQL:SET` | 2 | 2 | owned | io, ipc_rpc_bridges, state_mutation | pre-#2990, unchanged: SET :host-var = expr writes through the SQL boundary. |
| `CICS:INQUIRE` | 1 | 1 | blanket-only | blanket | same SPI-introspection reasoning as ASSIGN (0 real occurrences with a specific object; the crucible's one hit is a bare form). |
| `CICS:SIGNAL EVENT` | 1 | 1 | owned | events | pre-#2990, unchanged: publishes into the CICS event-processing channel. |
| `CICS:START TRANSID` | 1 | 1 | owned | concurrency, ipc_rpc_bridges | #2990: schedules another transaction to start (interval control's task-spawn form). |
| `NATIVE:CALL 'CEEDATM'` | 1 | 1 | owned | args, ipc_rpc_bridges, time_date_logic | #2990: same LE date/time service family as CEEGMT. |
| `NATIVE:CALL 'CEEGMT'` | 1 | 1 | owned | args, ipc_rpc_bridges, time_date_logic | #2990: an LE date/time service -- its calling convention always passes an output parameter, so args is a genuine property of this specific service call. |

## JCL coverage table

JCL required **no rule edit** — the pass confirmed every statement keyword and every dataset/EXEC
operand actually used in the corpus is owned or recorded, closing out the issue's requested sibling pass
with a table instead of a guess. One design note: the census originally treated `\b[A-Z]{2,10}=` as a
JCL operand anywhere in the file, which swept up an entire CICS SIT-parameter deck
(`cics-banking-sample-application-cbsa/DFH$SIP1.jcl`, no `//` anywhere — not JCL syntax at all) as if its
`AICONS=`/`KEYRING=`/`GRPLIST=` lines were JCL vocabulary. The census now requires a real `//` statement
line; the resulting long tail of genuine `EXEC PROC=...,SYM=val` symbolic overrides whose names are
site- or application-defined (each on 1-2 files) is bucketed into one row rather than given one row per
site-specific symbol name — see Follow-up #2 for the surface this still leaves unowned.

### jcl

| verb | n | files | verdict | owner rule(s) | reason |
|---|---|---|---|---|---|
| `STMT:DD` | 1308 | 126 | owned | io | io's real anchor requires the SAME line/continuation to carry DSN=/SYSOUT=; a DD DUMMY, in-stream `DD *`, or a DD covered entirely by a preceding JOBLIB/STEPLIB carries no target and legitimately dilutes this coarse per-statement bucket below the usual verb-level threshold -- the io_rule_contract's own C5 (a job-local temporary crosses no boundary). |
| `OPERAND:DISP=` | 531 | 116 | owned | cleanup, io, sync_locks | pre-#2990, unchanged: DISP names the allocation (io); OLD/MOD is jcl's serialization primitive (#2733); a DELETE disposition is teardown (#2749). Each sub-share is well below 90% alone because most DISP values are the plain SHR/NEW/CATLG forms that trigger none of the three -- the three are read together, not required each on their own. |
| `OPERAND:DSN=` | 499 | 111 | owned | io | pre-#2990, unchanged: the dataset name is io's own anchor keyword. |
| `STMT:EXEC` | 389 | 187 | owned | func_start | pre-#2990, unchanged: an EXEC statement is a callable unit (func_start's contract). |
| `OPERAND:SYSOUT=` | 378 | 111 | owned | io | pre-#2990, unchanged. |
| `OPERAND:UNIT=` | 250 | 30 | none | — | a device/unit-type allocation attribute; no cross-language rule owns device selection. The cleanup/sync_locks noise (<1% each) is DISP=(...,DELETE)/DISP=OLD sharing the same continuation line, not UNIT= itself. |
| `OPERAND:SPACE=` | 233 | 41 | none | — | a space-allocation attribute (primary/secondary extents); no cross-language rule owns storage sizing. The sync_locks/state_mutation/globals noise (~2% each) is other operands on the same continuation line, not SPACE= itself. |
| `OPERAND:PGM=` | 194 | 125 | owned | func_start | pre-#2990, unchanged: PGM= is the EXEC step's callable unit. |
| `PGM:*` | 191 | 125 | owned | func_start | pre-#2990, unchanged: PGM= is func_start's callable unit; a minority also names one of #2751's command-executor programs (high_risk_execution, 34%) or carries COND=/PARM= on the same line (safety/args) -- real but not universal co-occurrences, not claims about PGM= itself. |
| `OPERAND:MEMBER=` | 177 | 51 | owned | import | pre-#2990, unchanged for `// INCLUDE MEMBER=` (import's target). This corpus's MEMBER= keyword is also a plain PROC/utility parameter unrelated to INCLUDE (e.g. IEBCOPY's MEMBER= card) on ~44% of occurrences, co-occurring with func_start instead -- two distinct statement shapes sharing one keyword, not import failing to fire. |
| `STMT:JOB` | 119 | 119 | owned | class_start | pre-#2990, unchanged: the JOB card is jcl's program-unit exception, the cobol-family precedent. |
| `OPERAND:NOTIFY=` | 116 | 116 | owned | class_start | pre-#2990: NOTIFY= sits on the JOB card, so class_start's capture (which spans the whole card) fires alongside it -- an artifact of the census unit, not a claim that NOTIFY= itself is class_start's. telemetry co-occurs on ~37% (the JOB card also carries MSGCLASS=/CLASS=) but is not required. |
| `OPERAND:<installation- or application-specific>` | 106 | 23 | owned | func_start | #2990: a catch-all for `EXEC PROC=name,SYM1=val1,...` keyword symbolic overrides whose names are site- or application-defined (APPLID=, GRPLIST=, KEYRING=, dozens more, each 1-2 files) -- real `//` statement operands, but not JCL language vocabulary; bucketed rather than given one row per site-specific symbol name. Most co-occur with func_start (they ride the same EXEC/PROC step as PGM=/PROC=) at well under the single-verb threshold because the bucket spans many unrelated PROCs. |
| `OPERAND:REGION=` | 105 | 80 | none | — | a step/job memory-region-size attribute; no cross-language rule owns memory sizing. It sits on the same JOB/EXEC card as MSGLEVEL=/MSGCLASS= (telemetry, 52%) and PGM=/PROC= (func_start, 38%) often enough to show up as noise, but neither reaches a share that makes REGION= itself their owner. |
| `STMT:INCLUDE` | 96 | 48 | owned | import | pre-#2990, unchanged: INCLUDE MEMBER= is jcl's dependency-inclusion statement. |
| `OPERAND:MSGCLASS=` | 83 | 83 | owned | telemetry | pre-#2990, unchanged: telemetry's own operand. class_start co-occurs on 65% of occurrences (the JOB card) but is not required. |
| `OPERAND:ORDER=` | 82 | 82 | none | — | JCLLIB ORDER='s library list; same reasoning as the JCLLIB statement itself -- a reference, not a declaration. |
| `STMT:JCLLIB` | 82 | 82 | none | — | JCLLIB ORDER= names a search library for later INCLUDE/PROC lookups -- it binds no unit itself (import corollary 1: a reference is not a declaration), same reasoning as JOBLIB not being `import` in cobol. |
| `OPERAND:CLASS=` | 73 | 73 | owned | telemetry | pre-#2990: the JOB card's output class -- telemetry's observability-dial family. class_start co-occurs on 85% (the JOB card) but is close enough to the floor that it is not separately required. |
| `OPERAND:BLKSIZE=` | 71 | 29 | owned | io | a DCB attribute; io fires only when it rides the same continuation as a fresh DSN=/SYSOUT= (25%) -- most BLKSIZE= values in this corpus modify a DD that references another dataset's DCB (DCB=*.step.dd) and inherit that boundary instead of opening a new one. |
| `OPERAND:RECFM=` | 60 | 27 | owned | io | same DCB-attribute reasoning as BLKSIZE= -- io fires only when it rides the same continuation as a fresh DSN=/SYSOUT=. |
| `OPERAND:DSORG=` | 56 | 24 | owned | io | same DCB-attribute reasoning as BLKSIZE=/RECFM=. |
| `OPERAND:MSGLEVEL=` | 53 | 53 | owned | telemetry | pre-#2990, unchanged: what the job log records -- telemetry's own operand. |
| `OPERAND:VOL=` | 53 | 5 | none | — | a volume-serial allocation attribute; no cross-language rule owns 'which physical volume'. |
| `OPERAND:PARM=` | 48 | 27 | owned | args | pre-#2990, unchanged: PARM= is the EXEC step's parameter (args). func_start co-occurs on 67% (the same EXEC step) but is not separately required. |
| `OPERAND:DYNAMNBR=` | 47 | 35 | owned | func_start, high_risk_execution | #2751: DYNAMNBR only ever appears on the same EXEC step as one of the command-executor programs (IKJEFT01 etc.) this corpus plants -- co-occurrence, not a claim that DYNAMNBR itself is dangerous. |
| `OPERAND:LRECL=` | 45 | 24 | none | — | a DCB record-length attribute; no cross-language rule owns record-length. |
| `OPERAND:DCB=` | 43 | 22 | owned | io | references another dataset's DCB attributes on the same DD -- io fires only when that DD ALSO carries its own fresh DSN=/SYSOUT= on the same continuation window (42%); a DCB=*.step.dd cross-reference alone inherits the target rather than opening one. |
| `OPERAND:OUTLIM=` | 43 | 24 | owned | io | pre-#2990, unchanged: a SYSOUT limit -- io's own operand family. |
| `STMT:SET` | 41 | 13 | owned | globals, state_mutation | pre-#2990, unchanged: a job-wide symbol assignment is both a write and the creation of shared state (#2750's dual). |
| `OPERAND:COND=` | 37 | 20 | owned | safety | pre-#2990, unchanged: a return-code test -- jcl's error-handling idiom. |
| `OPERAND:DSNAME=` | 33 | 6 | owned | io | the long form of DSN= -- same boundary. This corpus's 33 occurrences are concentrated in 6 files, so the share is noisier than DSN='s 499-occurrence spread. |
| `STMT:ENDIF` | 31 | 26 | none | — | a block closer, same class as cobol's END-* terminators -- structure, not a second decision. |
| `STMT:IF` | 31 | 26 | owned | branch | pre-#2990, unchanged. |
| `OPERAND:DSNTYPE=` | 29 | 18 | none | — | a dataset-type qualifier (PDS/PDSE/LIBRARY); no cross-language rule owns dataset-type classification. |
| `STMT:ELSE` | 24 | 23 | owned | branch | pre-#2990, unchanged. |
| `OPERAND:OUTC=` | 20 | 12 | none | — | a SYSOUT class override distinct from the JOB card's CLASS=; no dedicated rule, and it never co-occurs with telemetry at this corpus's sample size. |
| `OPERAND:PROC=` | 19 | 11 | owned | func_start | the keyword form of `EXEC PROC=name` -- same callable-unit contract as bare `EXEC name`. |
| `OPERAND:RMODE=` | 19 | 11 | owned | func_start | co-occurs with func_start (the binder attribute rides the same EXEC step as PGM=/PROC=); not a claim RMODE= itself is a callable unit. |
| `OPERAND:JAVADIR=` | 18 | 8 | none | — | a fixed keyword parameter of the CICS Web Services bind utility PROC (DFHWBSVC/DFHWBTUP); real, recurring vocabulary across this corpus's 8 CICS Explorer samples, but application/product-specific, not JCL language vocabulary -- no cross-language rule owns it. |
| `OPERAND:PATHPREF=` | 18 | 8 | none | — | a fixed keyword parameter of the CICS Web Services bind utility PROC (DFHWBSVC/DFHWBTUP); real, recurring vocabulary across this corpus's 8 CICS Explorer samples, but application/product-specific, not JCL language vocabulary -- no cross-language rule owns it. |
| `OPERAND:TMPDIR=` | 18 | 8 | none | — | a fixed keyword parameter of the CICS Web Services bind utility PROC (DFHWBSVC/DFHWBTUP); real, recurring vocabulary across this corpus's 8 CICS Explorer samples, but application/product-specific, not JCL language vocabulary -- no cross-language rule owns it. |
| `OPERAND:TMPFILE=` | 18 | 8 | none | — | a fixed keyword parameter of the CICS Web Services bind utility PROC (DFHWBSVC/DFHWBTUP); real, recurring vocabulary across this corpus's 8 CICS Explorer samples, but application/product-specific, not JCL language vocabulary -- no cross-language rule owns it. |
| `OPERAND:USSDIR=` | 18 | 8 | none | — | a fixed keyword parameter of the CICS Web Services bind utility PROC (DFHWBSVC/DFHWBTUP); real, recurring vocabulary across this corpus's 8 CICS Explorer samples, but application/product-specific, not JCL language vocabulary -- no cross-language rule owns it. |
| `OPERAND:SYMBOLS=` | 15 | 11 | none | — | a loader symbol-table option; no cross-language owner. |
| `STMT:PROC` | 14 | 14 | owned | api | pre-#2990, unchanged: a PROC declaration is jcl's callable surface (the api contract's fallback family). |
| `OPERAND:HLQ=` | 10 | 9 | owned | globals, state_mutation | a `// SET HLQ=` high-level-qualifier symbol -- same dual as the SET statement itself. |
| `STMT:NOTIFY` | 10 | 10 | none | — | the standalone `// NOTIFY user` job-completion-mail statement (distinct from the JOB card's NOTIFY= operand below); no cross-language rule owns 'notify on completion'. |
| `OPERAND:TIME=` | 8 | 8 | owned | func_start | a step time limit; co-occurs with func_start (the same EXEC step) on 7 of 8 occurrences -- the corpus's smallest reliably-attributed operand sample. |
| `OPERAND:DDNAME=` | 6 | 4 | none | — | cross-references another DD's name (e.g. for SYSOUT routing); no dedicated rule, and this corpus's 4 files show no consistent co-occurrence. |
| `OPERAND:SRC=` | 6 | 6 | owned | api, args, func_start | a build-utility PROC's source-member keyword parameter; co-occurs with func_start/args/api the same way PARM= does (each at exactly half of this tiny 6-occurrence sample). |
| `STMT:PEND` | 6 | 6 | none | — | closes an in-stream PROC; a closer, not a second declaration -- same reasoning as PROC's own doc note. |
| `OPERAND:BLK=` | 4 | 4 | owned | globals, state_mutation | a `// SET BLK=` symbol -- same SET dual. |
| `OPERAND:CMPLLIB=` | 4 | 4 | owned | globals, state_mutation | a `// SET CMPLLIB=` symbol -- same SET dual (3 of its 4 occurrences). |
| `OPERAND:MBR=` | 4 | 4 | owned | args | a PROC's member-name keyword parameter -- same PARM=/PROC= family. func_start co-occurs on 3 of 4 occurrences but is not separately required. |
| `OPERAND:MEMLIMIT=` | 4 | 4 | none | — | a step memory limit; no dedicated rule, and its 4 occurrences show no consistent co-occurrence. |
| `OPERAND:START=` | 4 | 3 | none | — | a PROC's step-start-point override (restart control); no dedicated rule. |
| `OPERAND:LIBPRFX=` | 3 | 3 | owned | api, args | a build-utility PROC's library-prefix keyword parameter -- same PARM=/PROC= family. |
| `OPERAND:LINKLIB=` | 3 | 3 | owned | globals, state_mutation | a `// SET LINKLIB=` symbol -- same SET dual. |
| `OPERAND:LNGPRFX=` | 3 | 3 | owned | api, args | same build-utility PROC-parameter family as LIBPRFX= |
| `STMT:EXPORT` | 2 | 2 | owned | globals | pre-#2990, unchanged: EXPORT SYMLIST= makes symbols visible to in-stream data -- shared state. |

## Findings filed (not fixed here — each is a scope call, argued in its own issue)

1. **language-crucible#26** — add the three `cicsdev` async-API sample repos used above to the pinned
   corpus in its own release (Apache-2.0; provenance rows for `SOURCES.md`) — a pin bump is its own
   cross-repo workflow (`docs/ecosystem.md`), not folded into this engine PR.
2. **gitgalaxy#3002** — JCL in-stream payload grammar: SQL DCL/DDL and IDCAMS/DSN utility commands under
   `//SYSIN DD *` (`GRANT` 24, `DROP` 17, `DELETE` 15, `RUN PROGRAM` 33 occurrences in the crucible) have
   no owner. The step-level posture (#2751/#2486: JCL's callable unit is the step, not its payload)
   argues against a rule here, but the surface is real and undocumented until this issue.
3. **gitgalaxy#3003** — idiom-wrapper tracking. The issue's own follow-up comment cites `temporal-crucible`'s
   finding that curl's 8.17→8.18 `curlx` allocator-wrapping refactor made summed `state_memory_alloc`
   drop 86% in one release with LOC still growing — literal vocabulary matching goes blind the moment a
   project wraps its own idioms. This pass found the COBOL analogue is currently mild (carddemo's
   `CSUTLDTC` date-utility wrapper is a `CALL` site, still counted; **zero** of the corpus's 591 COBOL
   files hosts an `EXEC CICS` block inside a copybook rather than a program, so the specific
   program-level-blindness shape the curl case describes does not reproduce here today) — but the
   cross-cutting design question (should the engine track project-local wrapper vocabularies at all, and
   how) is real and belongs in its own issue, not a COBOL-scoped one.
4. **gitgalaxy#3004** — COBOL's auth surface (`SIGNON`/`SIGNOFF`, `VERIFY PASSWORD`, `QUERY SECURITY`,
   `EXEC SQL GRANT`/`REVOKE`) has no owner in the base schema. Worth a question to whichever issue governs
   the appsec pack's `auth_middleware` (`def_auth`) — is a per-language `auth`-family signal in scope, or
   is this deliberately out of the base 49-key schema.
5. **gitgalaxy#3005** — found while blessing this PR's golden master, unrelated to it: the committed
   fixtures were already ~8480 diffs drifted from a clean scan of the exact pinned corpus, entirely in
   git-history-derived signals (Architect/Churn/Authorship Centralization) for files this PR never
   touches. Both fixtures here were blessed by diffing an unmodified-engine scan against this branch's
   scan of the *identical* corpus checkout and patching only the leaves that differ between those two —
   never the raw `crucible_check.py --update` output — so none of that pre-existing drift is in this PR.

## Acceptance

`python tests/tools/embedded_verb_coverage.py cobol --check --extra <cicsdev repos>` and
`python tests/tools/embedded_verb_coverage.py jcl --check` both exit 0: every verb/idiom this pass's
census finds in the corpus is either owned by a semantic rule or recorded blanket-only/none with a
one-line reason, closing #2990's stated acceptance criterion.
