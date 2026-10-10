---
description: "A proof here says one thing: **on these scenarios, the Java port gave the same outputs as the COBOL program run by"
---
# The oracle and its assumptions: where our COBOL side may differ from IBM z/OS

A proof here says one thing: **on these scenarios, the Java port gave the same outputs as the COBOL program run by
our oracle.** The oracle is GnuCOBOL 3.1.2 (`cobc -std=ibm -fsign=EBCDIC`), plus our own models of what GnuCOBOL
lacks: CICS (`tests/equivalence/cics/ggcics.c`), Db2's precompiler (`tests/tools/equivalence_sql.py`, over a real
Db2), Language Environment services (`tests/equivalence/le/`) and IBM's DISPLAY text (`tests/equivalence/faults/ggdisplay.c`).

So every claim rests on three links:

1. **IBM z/OS ≈ our oracle.** This document.
2. **Our oracle = the Java port**, on the scenarios run. The proofs.
3. **The scenarios exercise the program.** The coverage figures quoted with every proof.

Link 1 is the only one that no run of ours checks. This page lists every place we know or suspect it does not
hold, so that a claim can be quoted with its limits. A run on real z/OS would settle most entries; until then each
one is either made to match IBM's documentation, refused by name, or written down here.

## The oracle is pinned and recorded (#4309)

`tests/equivalence/gnucobol.Dockerfile` pins the oracle, so every proof names the same GnuCOBOL:

| pinned | value |
|---|---|
| base image | `debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251` |
| `gnucobol3` / `libcob4` (Debian package) | `3.1.2-5+b1` |
| `cobc --version` | `cobc (GnuCOBOL) 3.1.2.0` (the build fails if the installed compiler prints anything else) |

The image carries the three values as labels (`org.gitgalaxy.oracle.*`). `tests/tools/equivalence_oracle.py` reads
the image a run uses -- its id, labels, `cobc --version` and the installed package -- and compares it with the pin.
Every proof report (`equivalence.py run`, the CALL and CICS harnesses, `cics_crucible.py` results and
`--report-dir` proofs) records that fingerprint under `oracle`, with `matches_pin` and any `mismatches`. A
mismatch (an image built before the pin, a `--build-arg` override) is a warning locally and stops the run under
`GITGALAXY_ORACLE_STRICT=1`, which the CICS crucible workflow sets. `gnucobol-db2.Dockerfile` builds `FROM` the
oracle image, so a Db2 case's image inherits the pin and its labels; it is built once and kept, so after the oracle
moves, `docker rmi gitgalaxy-gnucobol-db2:3` before the next Db2 run.

Moving the oracle is a deliberate change: bump the three `ARG`s together, rebuild, and re-prove (a changed oracle
makes every proof's evidence stale). If Debian drops the pinned package from `deb.debian.org` at a point release,
the pinned build fails (the weekly CICS crucible run notices); restore it from `snapshot.debian.org` rather than
taking whatever version is current.

## The Db2 image is pinned (#4733)

A Db2 case runs its SQL on one real Db2 (IBM Db2 Community Edition, in a container), the COBOL side through IBM's CLI
driver and the Java side through JDBC (`tests/tools/equivalence_db2.py`). The image was `icr.io/db2_community/db2:latest`,
a tag that moves: a new Db2 could change a code page, a collation or a SQLCODE with no change of ours. It is now named
by content digest:

| pinned | value |
|---|---|
| Db2 image | `icr.io/db2_community/db2@sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6` |
| built | 2026-07-13 (the image every Db2 proof so far ran on; it was `:latest` on 2026-10-08) |

`equivalence_db2.IMAGE` is the pin. `tests/cobol_mainframe/test_db2_image_pin.py` fails when it is a tag, or when this
page does not name its digest. A container left running from another image is refused (`docker rm -f gitgalaxy-db2`),
and every Db2 case's proof report records the image under `oracle.db2`. `equivalence_db2.py` is part of the harness
fingerprint, so moving the pin makes every evidence record stale (re-proved by the Evidence Refresh bot).

Moving it is a deliberate change: resolve the new digest (`curl -sI -H 'Accept: application/vnd.oci.image.index.v1+json'
https://icr.io/v2/db2_community/db2/manifests/latest`, header `docker-content-digest`), set `IMAGE`, update this table,
and re-sweep the Db2 cases.

## Status key

| status | meaning |
|---|---|
| **MATCHED** | The oracle is made to behave as IBM documents it (a flag, a model or a shim), and a test pins it. |
| **REFUSED** | IBM's behaviour is not settled by its documentation, so the harness stops by name ("not modelled") and no proof rests on a guess. |
| **DIFFERS** | A known difference between the oracle and z/OS. The entry says whether any proven program reaches it. |
| **ASSUMED** | Believed to match, and not measured on z/OS. |

"Reached" means a proven program's scenarios execute the behaviour. An unreached difference cannot have changed a
verdict, but it limits what the proof says about inputs outside the scenarios.

## Summary

| id | area | entry | status | reached by a proof? |
|---|---|---|---|---|
| C1 | compiler | Binary truncation: `TRUNC(STD)` (IBM's default) on both sides (#4102, fixed); `TRUNC(OPT)` as STD for values that fit their PICTURE, a named stop otherwise (#4706) | MATCHED / MODELLED (OPT) | reachable (GenApp LGICDB01); OPT: CBSA CUSTCTRL, DELACC, INQACC run under it, no scenario reaches the stop |
| C2 | compiler | Arithmetic intermediates: the oracle truncates them (ARITHMETIC-OSVS), the det runtime the same way (#4287); where GnuCOBOL departs from IBM's decimal places | MATCHED (det runtime = oracle) / DIFFERS (oracle, GnuCOBOL's departures) | yes (INTCALC, POSTTRAN …); a departure: not known to be |
| C3 | compiler | An integer literal truncated to zero keeps no sign | DIFFERS | no |
| C4 | compiler | An unsigned binary taken below zero by ADD/SUBTRACT: IBM keeps the absolute value, and so does the det runtime; cobc's native arithmetic wraps (#4684) | MATCHED (det runtime = IBM) / DIFFERS (oracle vs IBM, declared; no cobc option turns it off) | no |
| C5 | compiler | `NUMPROC(MIG)` as Enterprise COBOL 5+ compiles it (NOPFD), `NUMPROC(PFD)` with preferred signs (#4271); `TRUNC(OPT)` with conforming binary values (#4706); `INTDATE(LILIAN)`, `ARITH(EXTEND)` | MATCHED (NUMPROC) / MODELLED (TRUNC(OPT), det ports; a stop by name past the PICTURE) / REFUSED (the rest) | NUMPROC: no; TRUNC(OPT): CBSA (det ports) |
| C6 | compiler | COMP-1 / COMP-2: IBM hexadecimal floating point, and float-mode evaluation of the whole expression | MODELLED in the det runtime (HFP, #4271 slice 1); the oracle DIFFERS (IEEE, decimal evaluation): proven by IBM-cited vectors and on exact values; what the oracle cannot decide REFUSED by name | no (DBB EPSMPMT: its float `**` is a hole) |
| C7 | compiler | COMP-5 byte order: little-endian vs z/OS big-endian | DIFFERS | read as numbers only (a VALUE beyond the PICTURE: fixed, #4501) |
| C8 | compiler | DISPLAY of signed zoned, binary and packed items | MATCHED | yes |
| C9 | compiler | POINTER is 8 bytes in GnuCOBOL (x86-64), 4 on z/OS | DIFFERS (declared: each side's fields read by its own layout, compared by name; a POINTER only as NULL or not) | only NULL (CBSA, data after one included) |
| C10 | compiler | INITIALIZE / VALUE ZERO zoned items: unsigned F zone (GnuCOBOL) vs preferred C sign (z/OS) | DIFFERS (tolerated where a case declares it) | yes (CardDemo READACCT ARRYFILE) |
| C11 | compiler | A non-digit in a numeric DISPLAY item: MOVEd from an alphanumeric item (#4049); MOVEd to a binary item (#4652); read as a MOVE sender, an operand, a comparand, and the sign rewrite of a signed sender (#4662) | DIFFERS (#4049: inputs kept out of the cases) / MODELLED, the oracle's rules (#4652, #4662) | yes (COMEN01C option `1!`; GenApp LGTESTP4's add) |
| C12 | compiler | FUNCTION RANDOM: the oracle's generator (glibc via GnuCOBOL), not IBM's unpublished one; a seed IBM does not allow refused | DIFFERS (the numbers) / ASSUMED (the interface) | yes (CBSA CRDTAGY1-5, INQCUST: cbsa-crdtagy1..5, cbsa-inqcust, seeds 0 and a stated `"taskn"`); translated, no proof yet (GenApp LGICVS01) |
| C13 | compiler | A numeric operand compared with a nonnumeric one (an alphanumeric, alphabetic or numeric-edited item): compared as its characters, not by value (#4665) | MATCHED (unsigned integer literals as written; zoned, packed and binary items as their digits, sign dropped; non-integer ones as the oracle's digits) / REFUSED (a signed literal, a SIGN SEPARATE or P-scaled item, an arithmetic expression, an equality with a literal of more decimal places than an edited item) | yes: CardDemo COTRTLIC (proven; an alphanumeric item against `0`); no proven program compares an edited item with a number |
| C14 | compiler | Size errors without ON SIZE ERROR: a zero divisor leaves the receivers unchanged in the oracle (libcob's NaN), the det runtime the same (#4655); z/OS's result is undefined (a decimal-divide exception); 0 ** a negative is 0 in the oracle, a size error on z/OS | MATCHED (det runtime = oracle) / DIFFERS (oracle vs z/OS) | not known to be: no proven scenario divides by zero |
| C15 | compiler | `CALL identifier`: the port dispatches over the program names the item can hold, found from the source (VALUE, VALUE table, MOVEs of literals); uppercase names of up to 8 characters; any other value, write or name refused by name (#4736) | MODELLED where the names are known, REFUSED where they are not | yes (end-to-end test against cobc; DBB EPSCSMRT translates whole, its callee EPSMPMT is refused) |
| C16 | compiler | A 1- or 2-digit COMP-5 item: one byte in GnuCOBOL, a halfword on z/OS (and in the det layout), so offsets, record lengths and a value past the byte differ; no cobc option changes it (#4751) | DIFFERS (oracle vs IBM, declared) / REFUSED (the oracle refuses such a program by name) | no: no corpus or case declares one |
| D1 | data | Text order is ASCII (Latin-1), not EBCDIC | DIFFERS | keys: no; comparisons: not audited |
| D2 | data | Hex literals that name EBCDIC characters (`X'40'`); a hex literal is its raw bytes under every record charset, the SYSOUT record separator a plain LF (#4698) | DIFFERS (oracle vs IBM, characters) / MATCHED (the bytes, the oracle = the port = IBM) | yes (batch Sysout byte test, 4 record charsets) |
| D3 | data | Zoned signs in ASCII data (`{`, `}`, A–R overpunch) | MATCHED | yes |
| D4 | data | An alphanumeric literal holding a character no single-byte code page holds (a UTF-8 em dash): the statement is a hole by name, the program translates; in a VALUE, a national / DBCS literal or a name the program stays refused (#4272) | REFUSED (the statement) | no |
| F1 | files | Natural FILE STATUS values come from GnuCOBOL's BDB files | ASSUMED | yes (00, 10, 23, 22) |
| F2 | files | Fault FILE STATUS values are injected on both sides | MATCHED | yes |
| F3 | files | RECFM=VB: records compared by content, framed as GnuCOBOL frames them, not as a z/OS RDW | ASSUMED | yes (CardDemo READACCT VBRCFILE) |
| F4 | files | JCL utility steps (SORT, IDCAMS, IEBGENER) are not run; the COBOL SORT / MERGE verbs are translated (#4268) | REFUSED (utility steps) | — |
| X1 | CICS | Commands, RESP/RESP2 and EIB from IBM's API reference | ASSUMED | yes |
| X2 | CICS | Screens compared as the symbolic map, not the 3270 stream | ASSUMED | yes |
| X3 | CICS | Backout: recoverable files and Db2 undone, RECOVERY(NONE) files kept | MATCHED | yes (CBSA INQACC) |
| X4 | CICS | A task takes no time (ASKTIME = dispatch time) | ASSUMED | yes |
| X5 | CICS | Options and conditions IBM leaves open are refused | REFUSED | — |
| X6 | CICS | WRITEQ with a LENGTH past its FROM item (GenApp LGSTSQ): the task is judged up to the refused WRITEQ (owner decision on #4607); not settled on z/OS (#4050) | REFUSED (the WRITEQ) / judged up to it | yes (GenApp LGACDB01, LGACDB02, LGDPDB01, LGIPDB01, LGUCDB01 error paths) |
| X7 | CICS | ASSIGN INVOKINGPROG / PROGRAM; LINKed programs run in one task | MATCHED | yes (GenApp LGUPDB01) |
| X8 | compiler | A reference modification past its item (no SSRANGE): a storage overlay | not run | no |
| X9 | CICS | Named counters (GET COUNTER) | MATCHED | yes (GenApp LGACDB01) |
| X10 | CICS | A LINK target's COMMAREA bytes past the end of the caller's record | DIFFERS | no |
| X11 | CICS | ASKTIME ABSTIME into a field narrower than S9(15) COMP-3 (GenApp's WS-ABSTIME) | DIFFERS | yes (GenApp error paths, #4173) |
| X12 | CICS | A task with no COMMAREA that MOVEs DFHCOMMAREA anyway | UNDEFINED, masked | yes (DBB EPSCMORT) |
| X13 | CICS | An ESDS browsed by RBA: fixed-length records, a record's RBA its byte offset; RBAs that address no record refused | ASSUMED (REFUSED where IBM is silent) | yes (DBB EPSMLIST) |
| X14 | CICS | READ ... INTO LENGTH: in-out, truncation and LENGERR; a VSAM file's LENGTH need not equal its record length; LENGERR on READ UPDATE refused | ASSUMED (REFUSED where IBM is silent) | yes, NORMAL only (GenApp LGUCVS01 / LGUPVS01) |
| X15 | CICS | Terminal RECEIVE (INTO / SET, LENGTH, MAXLENGTH, NOTRUNCATE; LENGERR, EOC on an LUTYPE2 terminal) and SEND CONTROL | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-terminal-receive, hc-terminal-eoc) |
| X16 | CICS | HANDLE AID, IGNORE CONDITION, PUSH / POP HANDLE and HANDLE CONDITION ERROR on the det port | MATCHED (REFUSED where IBM is silent) | yes (cics-crucible hc-handle-aid, hc-ignore-error, hc-eoc-error) |
| X17 | CICS | Channels and containers: PUT / GET / DELETE CONTAINER, LINK / XCTL CHANNEL, ASSIGN CHANNEL; bytes never converted; CCSID options, SET, BYTEOFFSET, RETURN CHANNEL, MOVE and browse refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible ca-channel-containers, unreleased) |
| X18 | CICS | Interval control on the det port: START (INTERVAL / TIME / AFTER / AT, TERMID, REQID, PROTECT, FROM, RTRANSID / RTERMID / QUEUE), RETRIEVE (INTO / LENGTH, the data options, ENVDEFERR), CANCEL REQID, RUN TRANSID CHILD; TIME RESP2 and the order of out-of-range checks assumed; FETCH, RUN / START CHANNEL, RETRIEVE SET / WAIT refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible gt-start-retrieve, gt-terminal-coalesce, gt-start-options, unreleased) |
| X19 | CICS | ASSIGN on the det port: STARTCODE (TD / S / SD), USERID (the default user), FACILITY / SCRNHT / SCRNWD (INVREQ RESP2 5 without a terminal) from facts the harness states; no data area written when ASSIGN raises INVREQ; OPID, NETNAME, TERMCODE, FCI, the other screen sizes, work-area lengths and the rest refused | ASSUMED (REFUSED where the harness cannot decide) | yes (cics-crucible gt-assign-startcode, unreleased) |
| X20 | CICS | SEND TEXT on the det port and the stub: TERMINAL accepted as the default output disposition (the principal facility; the event is that of SEND TEXT without it); ACCUM, PAGING, SET, REQID, HEADER, TRAILER, JUSTIFY / JUSFIRST / JUSLAST, the printer, partition and LDC options, MSR, FMHPARM, DEFAULT / ALTERNATE refused | MATCHED (REFUSED where the region cannot decide) | yes (cics-crucible gt-send-text-terminal, unreleased) |
| X21 | CICS | EIBTASKN: the task's number is a stated fact of the run (`$GGCICS_TASKN` / `CicsTask.withTaskNumber`, a case's or scenario's `"taskn"`, default 0), not the number CICS assigns; a value outside 0 to 9,999,999 refused | DIFFERS (the value) / MATCHED (both sides) | yes (every CICS task; read by CBSA's Db2 programs, GenApp LGICDB01) |
| X22 | CICS | READ GTEQ / GENERIC on a KSDS: the first record whose key (or its first KEYLENGTH bytes) equals RIDFLD's or, with GTEQ, is greater, in the browse's key order (D1); NOTFND RESP2 80; READ UPDATE holds the record found; RIDFLD not updated; a GENERIC KEYLENGTH not shorter than the key or not above zero, a non-constant KEYLENGTH and a RIDFLD shorter than the key searched refused | ASSUMED (REFUSED where IBM is silent or the layout decides) | yes (GenApp LGICVS01 genapp-lgicvs01) |
| X23 | CICS | A COMMAREA of a stated length (a scenario's `commarea_length`, EIBCALEN shorter than the record): the program is given exactly those bytes; a reference past EIBCALEN refused on both sides, the task judged up to it | ASSUMED (REFUSED past EIBCALEN) | yes (GenApp LGACDB01, LGACDB02, LGDPDB01, LGIPDB01) |
| X24 | CICS | A task started with a channel (a scenario's `channel`: what a RUN TRANSID CHANNEL parent or a LINK CHANNEL caller passed), made its first program's current channel; the containers left on that channel compared at the task's end (dropped on an abend), byte for byte; RUN TRANSID children not run | ASSUMED | yes (async credit-card CRDTCHK, CSSTATS2, CSSTATUS, GETADDR, GETNAME; CBSA CRDTAGY1-5, an explicit CHANNEL(CIPCREDCHANN)) |
| X25 | COBOL layout | SYNCHRONIZED slack bytes in the layout model (GalaxyIR `record_layout`, `_storage_spans`): IBM Enterprise COBOL boundaries (halfword up to 4 digits, fullword above, the 8-byte binary S9(10)-S9(18) included; COMP-1 / INDEX / pointers fullword; COMP-2 doubleword) counted from the record, the table slack of IBM's rule; GnuCOBOL / Micro Focus may align an 8-byte binary on a doubleword | ASSUMED (IBM's fullword; z/OS is the target) | no (no committed case reaches an 8-byte SYNC binary) |
| X26 | CICS | BIF DEEDIT FIELD [LENGTH] edited in place in the region's EBCDIC page (CCSID 037); INQUIRE / SET TERMINAL UCTRANST as the CVDAs UCTRAN 450 / NOUCTRAN 451 / TRANIDONLY 452, the terminal's value stated by the run (the case TYPETERM's UCTRAN), a terminal RECEIVE after a SET refused; DFHVALUE(name) in the stub's programs is IBM's CVDA number; a DEEDIT field with no digit left, beyond 7-bit ASCII or past LENGTH, and the UCTRANST of a terminal other than the task's, refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-deedit-uctranst, unreleased; CBSA BNK1DCS's UCTRANST store / restore and the BNK1 screens' DEEDIT: cbsa-bnk1dcs, cbsa-bnk1cac ...) |
| X27 | CICS | RETURN TRANSID ... IMMEDIATE: the task of TRANSID attached at once with the COMMAREA, ahead of any terminal input and any START request, the terminal's next operator step left alone; its EIBAID is not stated by IBM (the crucible runner gives none and a case never reads it), its STARTCODE TD; INVREQ RESP2 1 (no terminal), INVREQ RESP2 2 (below the highest level), LENGERR RESP2 11 return to the program; LINK ... SYNCONRETURN accepted and ignored (IBM: "ignored if the link is local"); IMMEDIATE without TRANSID, and both INVREQs at once (no terminal below level 1), refused | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | yes (cics-crucible pc-return-immediate, unreleased; CBSA BNKMENU and the BNK1 screens' PF3, the task's terminal a case's `"termid"`: cbsa-bnkmenu, cbsa-bnk1cac ...) |
| X28 | CICS | FORMATTIME with RESP / RESP2: INVREQ RESP2 1 for an ABSTIME below zero, nothing formatted (without RESP the INVREQ's handling is refused at run time); ASKTIME with NOHANDLE and without ABSTIME (EIBDATE / EIBTIME as dispatched, X4); READQ TS ... LENGTH(LENGTH OF area): the most INTO takes, LENGERR truncation, no length stored back; RECEIVE MAP ... ASIS: input delivered as typed, lower case kept; an ABSTIME that is not packed decimal (the port reads the field by its declared usage), STRINGFORMAT (RESP2 2) and the output areas of an INVREQ FORMATTIME not modelled / not read | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-resp-options, unreleased) |
| X29 | CICS | INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID / ODUSERID / ODFACILNAME / ODNETWORKID / ODFACILTYPE: the task's own origin data, the five values the run states (a case's `origin`, for a task terminal input started; unstated, refused), the facility type as IBM's CVDA, a command with no origin option refused (INVREQ RESP2 2 is ambiguous); DELETEQ TS: the whole queue and its READQ NEXT position, QIDERR, INVREQ for a name of binary zeros, RESP2 0; QUERY COUNTER (COUNTER / POOL / VALUE): the value left unchanged, INVREQ RESP2 201 for a counter that is not there, a value beyond a fullword, MINIMUM / MAXIMUM / NOSUSPEND, a task number other than EIBTASKN and the origin of a task not started by terminal input refused; RECEIVE MAP ... TERMINAL: the task's terminal, as every RECEIVE MAP | ASSUMED (REFUSED where IBM is silent) | INQUIRE ASSOCIATION, DELETEQ TS, RECEIVE MAP TERMINAL: yes (cics-crucible hc-inquire-deleteq, unreleased; INQUIRE ASSOCIATION and RECEIVE MAP TERMINAL also CBSA BNK1CRA / BNK1DCS: cbsa-bnk1cra, cbsa-bnk1dcs, a case's `"origin"`); QUERY COUNTER: no (the reference region has no named counters; unit tests on both runtimes) |
| X30 | CICS | DEFINE COUNTER (COUNTER / POOL / VALUE; none: the initial value zero; a counter that exists: INVREQ RESP2 202; a pool or counter name outside IBM's characters: INVREQ RESP2 403 / 404) and DELETE COUNTER (a counter that is not there: INVREQ RESP2 201; a pool outside IBM's characters: 403); GET COUNTER and QUERY COUNTER answer INVREQ RESP2 201 for a counter that is not there (GET COUNTER answered NOTFND before: IBM lists none) and 403 / 404 for a bad pool / name; MINIMUM / MAXIMUM / NOSUSPEND / DCOUNTER, a VALUE below zero and a counter name of blanks refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-named-counters, unreleased) |
| X31 | CICS | SEND MAP / RECEIVE MAP for a map its mapset does not hold (MAPSET omitted: IBM defaults it to the MAP name, so `SEND MAP('BNK1CCM')` looks for map BNK1CCM in mapset BNK1CCM): abend ABM0, the transaction terminated, no condition raised (RESP / RESP2 / HANDLE CONDITION do not see it; a HANDLE ABEND exit does), recorded as an ABEND event with cause `system` | ASSUMED (REFUSED where IBM is silent: the mapset itself undefined, a non-constant name) | yes (cics-crucible hc-map-not-in-mapset, unreleased) |
| X32 | CICS | INQUIRE URIMAP's browse (START / NEXT / END with URIMAP, PATH, TRANSACTION: END RESP2 2 past the last definition, ILLOGIC RESP2 1 for a START while one is open; the installed definitions and their order are stated by whoever runs the task; a short value is padded with blanks; the areas are left alone on any condition other than NORMAL) and WRITE OPERATOR (TEXT only; recorded as a WRITE-OPERATOR event); the direct form INQUIRE URIMAP(name), every other URIMAP attribute, a NEXT / END with no browse, and a console text IBM reformats (DFHnnnn / DFHaannnn, or over 113 characters) refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible gt-urimap-browse, unreleased) |
| X33 | CICS | DOCUMENT CREATE (DOCTOKEN; none, TEXT / BINARY with LENGTH, or TEMPLATE: an empty document, the area's bytes unchanged, or the text the installed DOCTEMPLATE yields; LENGERR RESP2 1 for a negative LENGTH, NOTFND RESP2 3 for a template not installed) and DOCUMENT RETRIEVE (DOCTOKEN, INTO, LENGTH, MAXLENGTH, DATAONLY: at most MAXLENGTH bytes INTO, LENGTH the document's length, LENGERR RESP2 2 when truncated, NOTFND RESP2 1 for an unknown token, LENGERR RESP2 1 for a negative MAXLENGTH); the DOCTOKEN value, the installed templates' text, and the text a retrieved document's bytes are in are ours / stated by whoever runs the task; FROM, FROMDOC, SYMBOLLIST / LISTLENGTH / DELIMITER / UNESCAPED, DOCSIZE, HOSTCODEPAGE / CHARACTERSET, a RETRIEVE without DATAONLY or MAXLENGTH, a CREATE of TEXT / BINARY without LENGTH, a template with symbols or template commands, and DOCUMENT INSERT / SET / DELETE refused | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C; no cics-crucible case yet) |
| L1 | LE | CEEDAYS: documented pictures only | MATCHED / REFUSED | yes |
| L2 | LE | CEE3ABD abend codes | MATCHED | yes |
| L3 | LE | WORKING-STORAGE with no VALUE clause: GnuCOBOL's spaces vs LE's STORAGE option on z/OS | ASSUMED | yes (CardDemo READACCT OUTFILE, 2 bytes; CBSA CRDTAGY1-5 container-short, WS-CONT-IN past a short container) |
| A1 | assembler | CardDemo's COBDATFT, translated instruction for instruction; load-module-dependent paths refused | MATCHED / REFUSED | yes (CardDemo READACCT) |
| Q1 | Db2 | Db2 for Linux runs the SQL, not Db2 for z/OS | ASSUMED | yes |
| Q2 | Db2 | EXEC SQL keeps RETURN-CODE | ASSUMED | yes |
| Q3 | Db2 | The unit of work: one per CICS task; one per batch step, ended by EXEC SQL COMMIT / ROLLBACK (cursors closed as Db2 for z/OS closes them), backed out by an abend, with SAVEPOINT / ROLLBACK TO SAVEPOINT / RELEASE SAVEPOINT run by Db2; a CICS program's ROLLBACK refused (-926) | MATCHED | CICS: yes (CBSA XFRFUN); batch: yes (synthetic UOWDEMO, `tests/equivalence/db2/uow`, #4269) |
| Q4 | Db2 | WHENEVER, dynamic SQL, CONNECT, CALL, SCROLL cursors, host-variable arrays; a savepoint statement in a CICS program | REFUSED | — |
| Q5 | Db2 | DSNTIAC / DSNTIAR message formatting | REFUSED | no |
| Q6 | Db2 | Date and time text in ISO form; DDL adapted from z/OS jobs | ASSUMED | yes (CBSA, GenApp) |
| Q7 | Db2 | `CCSID EBCDIC` tables hold Unicode text: string order differs | DIFFERS | no |
| Q8 | Db2 | Positioned UPDATE / DELETE: the Java side by row id | MATCHED | yes (GenApp LGUPDB01) |
| Q9 | Db2 | More host variables than columns: SQLWARN3, the rest untouched | MATCHED | yes (GenApp LGUPDB01) |
| Q10 | Db2 | A statement the driver fails with no Db2 SQLCODE (a blank timestamp host variable) | REFUSED (the task; an enumerated fault task not judged) | yes (GenApp LGTESTP4: its add's enumerated fault task `add--sql-lgapdb01-316` (SELECT LASTCHANGED faulted), not run) |
| J1 | Java | VSAM files on H2, not the target database | ASSUMED | — |
| M1 | method | The scenarios are ours, not production traffic | — | — |
| M2 | method | SQL faults: injected on both sides at a statement (#4173), the SQLCA as the stub sets it | MATCHED (ASSUMED SQLCA) | yes (17 Db2 cases) |
| M3 | method | A LINKed program's COMMAREA result was not compared before 2026-10-02 | fixed | 7 cases re-proven |
| M4 | method | Clock fields: a value the run takes from the system clock | declared | yes (GenApp LGUPDB01) |

## Compiler: GnuCOBOL 3.1.2 `-std=ibm` vs IBM Enterprise COBOL

### C1. Binary truncation — MATCHED (fixed 2026-10-02, #4102)
- **What.** Under `TRUNC(STD)`, IBM's default, a binary item (COMP, COMP-4, BINARY) holds only its PICTURE's digits:
  `MOVE 99999` to `PIC S9(4) COMP` stores 9999, and `ADD 1` to 9999 raises ON SIZE ERROR. COMP-5 keeps its bytes.
- **Was.** `cobc -std=ibm` alone behaves as `TRUNC(BIN)`, and the harness passed no flag for STD; the det runtime ran
  BIN too. Both sides agreed, both differed from IBM.
- **Now.** The harness applies IBM's defaults for options nothing names: STD is GnuCOBOL's `-fbinary-truncate` (measured:
  +09999, SIZE ERROR, +02345). The det port sets each entry's TRUNC from the program's CBL / PROCESS cards, else the
  case's `compiler_options`, else STD, and restores the caller's on exit. Every det and model port was re-proven under
  it; nothing moved (no proven scenario puts more digits in a binary item than its PICTURE).
- **TRUNC(OPT) (#4706): MODELLED as STD with a stop.** "When TRUNC(OPT) is in effect, the compiler assumes that data
  conforms to PICTURE specifications in USAGE BINARY receiving fields in MOVE statements and arithmetic expressions.
  The results are manipulated in the most optimal way, either truncating to the number of digits in the PICTURE
  clause, or to the size of the binary field in storage (halfword, fullword, or doubleword)"; for data that does not
  conform "unpredictable results could occur ... dependent on the particular code sequence generated" (Enterprise
  COBOL for z/OS 6.x Programming Guide, "TRUNC"; the Language Reference's MOVE and arithmetic rules defer to the
  option). For conforming values the result is STD's. So the det runtime computes STD and **stops by name** --
  `TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable (<value> into a <n>-digit binary item) is not
  modelled` -- before a value past a COMP / COMP-4 / BINARY receiver's PICTURE is stored by a MOVE, an arithmetic
  store, or a typed (lifted) item's assignment (`Codec.truncOpt`, `Cobol.swapTruncOpt`; COMP-5 is never truncated
  and never stops). An ON SIZE ERROR statement stores nothing past the PICTURE (the receiver unchanged, as STD) and
  does not stop; a Db2 or CICS value assigned to a host variable by its byte width (#4579) is not a COBOL store and
  does not stop either. The oracle runs `-fbinary-truncate` (STD). A scenario that would reach such a value stops on
  the port's side, so it is never judged equal: the run fails with the stop's message (as `Hfp.divideNested` and the
  NUMVAL refusals), never a silent pass. A TRUNC(STD) program LINKed or CALLed from a TRUNC(OPT) one keeps the
  stop (a refusal where IBM's STD is defined, never a guess). A port without the stop -- a model port, the generated
  service -- is proven as TRUNC(STD): a declared difference of kind `option` in its evidence record
  (`equivalence_common.option_differences`). Pinned by `tests/cobol_mainframe/test_trunc_opt.py` (conforming values
  equal cobc's STD output; each non-conforming shape stops).
- **Typed (lifted) binary items (#4749, fixed).** A det port's typed binary item (a Java `long`, det-port B3) stores
  what its bytes would under every mode: a literal MOVE is folded at translation time only where STD, BIN and OPT
  agree (it fits the PICTURE; a COMP-5 item's bytes), an item MOVE is copied as is only where the receiver keeps
  every value the sender's bytes can hold, and anything else goes through the runtime's store under the run's TRUNC
  (`Cobol.binary`, as an arithmetic result). Before, a literal MOVE wrapped at the item's bytes and a same-size
  binary MOVE was copied as is under every mode (`MOVE 12345 TO PIC S9(3) COMP` held 12345, not STD's 345). A
  synced group's bytes are written back from its typed fields as they are (`Cobol.putBinary`), never stored again: a
  group MOVE that left X'FFFF' in a `PIC 9(4) COMP` keeps it (STD would have re-truncated it to 5535 on the next
  whole-group use, OPT would have stopped). Pinned by `tests/cobol_mainframe/test_lifted_binary_trunc.py` (bytes =
  typed = cobc `-fbinary-truncate` / `-fnotrunc`, signed / unsigned, COMP / COMP-4 / BINARY / COMP-5, halfword /
  fullword / doubleword, literal and item senders).
- **Reach.** GenApp's LGICDB01 moves the 10-digit CA-CUSTOMER-NUM into an `S9(9) COMP`: a customer number of 10 digits
  would now behave as on z/OS.

### C2. Arithmetic intermediates — the det runtime MATCHES the oracle (#4287); the oracle DIFFERS where GnuCOBOL departs from IBM
- **IBM's rule.** Enterprise COBOL keeps each intermediate result to a number of decimal places (6.4 Programming
  Guide, SC27-8714-03, Appendix A, "Fixed-point data and intermediate results"): `+ -` the larger of d1, d2; `*`
  d1 + d2; `/` the larger of the operands' difference and dmax, the most decimal places of any operand or receiver;
  at most 30 digits under `ARITH(COMPAT)`.
- **The oracle.** `cobc -std=ibm` turns on GnuCOBOL's `arithmetic-osvs` (`ibm-strict.conf`), so cobc truncates
  intermediates (`cob_decimal_align`) with decimal places it works out at compile time from those rules. The
  reproducer of #4287 is IBM's own: `COMPUTE R = A / B * C` with A = 1, B = 3, C = 300 and R `PIC 999V99` gives
  099.00 (A / B kept to 2 places). The 30-digit limit GnuCOBOL does not apply: ASSUMED that no proven intermediate
  is that long.
- **The det runtime (since #4287)** makes the same truncations: the translator replays cobc's decision
  (`det/osvs.py`, from GnuCOBOL 3.1.2's `cobc/typeck.c` and `cobc/tree.c`) and emits `Cobol.align(value, places)`
  where cobc emits `cob_decimal_align`; a literal on the right of an operation is libcob's decimal constant
  (`Cobol.Dc`); `Cobol.divide` keeps cob_decimal_div's 38 + max(d1 - d2, 0) places and `Cobol.power`
  cob_decimal_pow's trimming. COMPUTE, ADD / SUBTRACT / MULTIPLY / DIVIDE with an expression, and the relations of
  IF, PERFORM UNTIL, SEARCH WHEN and EVALUATE are planned; floating-point statements keep their HFP model (C6).
  Proven by `tests/cobol_mainframe/test_det_osvs.py` and by a randomized differential run (2026-10-07: over 100
  random programs, about 25,000 COMPUTE, ADD, SUBTRACT, IF and EVALUATE statements over zoned, packed and binary
  items, every output equal to the oracle's; on the earlier runtime about one line in six differed).
- **Where GnuCOBOL departs from IBM's rule** (each measured on the oracle; the det port does what the oracle does,
  so a proof cannot see them, and z/OS may not do them):
  - the stack of decimal places pairs an operation with its own operands only when every operand pushes its
    places; a binary item of scale 0, a short integer literal, ZERO and a literal on the right push nothing, and the
    operation then takes dmax or a neighbour's places: `COMPUTE R = XB + YB + Z` with two `PIC 9(4) COMP` items and
    R `PIC 999V99` aligns XB + YB to 2 places;
  - `cob_decimal_align` with fewer places than the target shifts the wrong way: the value loses as many low-order
    digits (579 aligned to 2 places is 500, so that COMPUTE gives 501.00 for 123 + 456 + 1; `- A + B` aligns 0 - A
    and loses A);
  - a literal's decimal constant takes the places of every intermediate it is added to or subtracted from, for the
    rest of the run, and an exponent literal loses its trailing zeros;
  - an EVALUATE leaves its dmax and stack to the next statements of the same sentence (a period, a COMPUTE or an IF
    resets them), and an IF's folded literal pair keeps it from walking its condition;
  - a relation of two literals with decimals compares wrongly (`100 > 1.25` is false), a separate GnuCOBOL matter:
    no case compares two literals.
- **Not replayed by the det translator** (refused by name, or exact as before): a negative literal exponent (libcob
  overwrites the constant: refused); an arithmetic expression in a PERFORM VARYING FROM / BY, a SEARCH ALL key or a
  subscript (cobc computes those otherwise); an EVALUATE whose last WHEN ends with a statement that leaves the state
  dirty (refused); statements inside ON SIZE ERROR phrases, which cobc parses before their statement's expression (their
  size-error semantics are C14's).
- **Reached.** Every COMPUTE with more than one operation, among them INTCALC's interest computation. Across the
  det sweep's ports (2026-10-07) the only truncation emitted is POSTTRAN's `ACCT-CURR-CYC-CREDIT -
  ACCT-CURR-CYC-DEBIT` to 2 places, a value of 2 places (no change); none of GnuCOBOL's departures is reached.
- **To settle.** A table of division, multiply-then-divide and binary-sum cases on z/OS against
  `tests/equivalence/rounding/RND.cbl` (and the departures above).

### C3. An integer literal truncated to zero — DIFFERS
- **What.** GnuCOBOL folds `MOVE -1000 TO PIC S9(3)` at compile time to +0 (`00{`). Every other truncating MOVE keeps
  the sign (`00}`). The translator matches GnuCOBOL (`gen.literal_moved`).
- **IBM's behaviour** is not measured. No proven program reaches it.

### C4. An unsigned binary below zero — the det runtime follows IBM (#4684); the oracle DIFFERS, declared
- **Policy** (owner, 2026-10-08, #4702): IBM is the reference, GnuCOBOL the instrument. Where IBM documents a result
  under the estate's compile options, the det port follows IBM and the oracle is configured to match; where no cobc
  option can, the shape is a declared oracle-vs-IBM difference that the comparator expects. A proof is never
  loosened.
- **IBM.** An unsigned receiver takes the absolute value: "If the receiving item is unsigned, no operational sign is
  generated for the receiving item and the absolute value of the sending item is used in the move" (Enterprise
  COBOL for z/OS 6.4 Language Reference, SC27-8713-03, MOVE statement, "Elementary moves", p. 404). That an
  arithmetic statement's store follows the same rule is not stated there in so many words: confirm (#4702). Under
  TRUNC(BIN), and for COMP-5 whatever TRUNC says, a binary receiver is "truncated only at halfword, fullword, or
  doubleword boundaries"; under TRUNC(STD) to "the number of digits in the PICTURE clause" (6.4 Programming Guide,
  SC27-8714-03, "TRUNC", pp. 419-420). So 1 - 3 into an unsigned `PIC 9(4) COMP` is 2 under either TRUNC. Not
  measured on z/OS here (#4702 Part 2). TRUNC(OPT) leaves an out-of-range value undefined: the det runtime stops on
  one by name (C1, #4706).
- **The oracle.** cobc 3.1.2 compiles `ADD` / `SUBTRACT ... TO / FROM` into native integer arithmetic
  (`cb_build_optim_add` / `_sub`) when the receiver is an unsigned binary item of no decimal places, the statement
  has no `ROUNDED` and no store option, and its one operand fits a C int (`cb_fits_int`: an integer literal within
  -2147483648..2147483647 -- `3.0` does not; a binary item of at most 4 bytes, a zoned one of at most 9 bytes, a
  packed one of at most 9 digits, all without decimal places; a list of literals is folded into one, a list naming an
  item is not). A store option means `ON SIZE ERROR` or `NOT ON SIZE ERROR` for COMP / COMP-4 / BINARY, only
  `ON SIZE ERROR` for COMP-5 (build_store_option), and for COMP / COMP-4 / BINARY also TRUNC(STD)
  (`-fbinary-truncate`), so under STD only COMP-5 goes native. The native result wraps modulo 2 ** bits: 1 - 3 is
  65534 in a halfword (a doubleword 18446744073709551614). Everything else -- `COMPUTE`, `GIVING`, `ROUNDED`,
  `ON SIZE ERROR`, an operand past a C int -- goes through libcob's decimal store, which keeps IBM's absolute value.
  A signed receiver wraps the same way on both paths (two's complement at its bytes, as IBM's TRUNC(BIN)).
- **No cobc option turns the native path off** (tried 2026-10-08 on the pinned image under TRUNC(BIN), with
  `-std=ibm`: `-O0`, `-O2`, `-fbinary-size=1-2-4-8` / `1--8`, `-fbinary-byteorder=native`, `-fnotrunc`,
  `-fno-constant-folding`, `-fno-arithmetic-osvs`, `-std=ibm-strict`, `-std=mvs`, `-debug`, `-fec=EC-SIZE*`; the
  `*.conf` entries have no such key). Only `-fbinary-truncate` keeps COMP / COMP-4 / BINARY off it, which is
  TRUNC(STD) itself. So the native wrap is a **declared oracle-vs-IBM difference**: the det runtime stores IBM's
  absolute value (`Cobol.storeNative` / `binaryNative` mark the statements cobc compiles natively,
  `gen.native_add`; a COMP-5 statement with a lone `NOT ON SIZE ERROR`, which cobc leaves unchecked, keeps IBM's
  size check). `test_det_binary_store.py` runs both TRUNC settings through both sides and expects the oracle's wrap
  and the port's absolute value on exactly the named lines (`DECLARED_C4`), equality on every other line. A proven
  case that reached the wrap would fail its compare; it is not tolerated.
- **Measured** 2026-10-08 (GnuCOBOL 3.1.2 `-std=ibm`, with and without `-fbinary-truncate`): COMP, COMP-4, BINARY
  and COMP-5, signed and unsigned, halfword / fullword / doubleword and scaled receivers, from `COMPUTE`, `ADD`,
  `SUBTRACT`, `MULTIPLY`, `DIVIDE ... ROUNDED`, `GIVING` and `MOVE`, with literal, binary, zoned and packed operands
  (about 4,000 stores). The det runtime matched every one but the native wrap. Two runtime fixes from that run follow
  IBM as well as the oracle: an unsigned doubleword (up to 2 ** 64 - 1 under TRUNC(BIN)) is not lifted to a Java
  long, and a lifted COMP-5 item keeps its bytes under TRUNC(STD).
- **Also measured, not modelled:** `MOVE` of a zoned sender whose digits, aligned to a TRUNC(STD) binary receiver's
  decimal places, pass 2 ** 64 (`MOVE` of `S9(20)V9(4)` holding 1234567890123456789 to `PIC 9V9(3) COMP`): libcob
  (`cob_move_display_to_binary`) accumulates them in an unsigned 64-bit integer that wraps before the PICTURE
  truncation, and stores 2.344; IBM and the det runtime store 9.000. COMP-5 and TRUNC(BIN) are not affected.
- **Reached.** No case reaches either. `test_det_programs.py` keeps its unsigned item above zero.

### C5. Compiler options: NUMPROC MATCHED where IBM pins it (#4271); TRUNC(OPT) MODELLED (#4706); INTDATE(LILIAN), ARITH(EXTEND) REFUSED
- **NUMPROC(MIG): MATCHED for Enterprise COBOL 5 and later.** "Enterprise COBOL 5 and 6 does not support the
  NUMPROC(MIG) option. If NUMPROC(MIG) is specified, Enterprise COBOL 5 or 6 issues a warning message and the
  compilation will get the default setting for NUMPROC. This is either the user-customized default or the IBM default,
  which is NUMPROC(NOPFD)" (Enterprise COBOL for z/OS 6.4 Migration Guide, GC27-8715-03, Table 18; the same in the 5.2
  Migration Guide, GC14-7383-03). A case states the compiler its estate builds with (`"compiler": {"product":
  "Enterprise COBOL", "version": "6.1", "evidence": ...}`); MIG then compiles as NOPFD on both sides
  (`equivalence_common.numproc_mig`; the det translator's `program.numproc_pfd`). The installation default is ASSUMED
  to be IBM's. **Refused:** MIG for a case that states no compiler or one before version 5, whose MIG was OS/VS
  COBOL's sign processing, documented only as "similar to" it.
  - IBM DBB MortgageApplication's EPSMPMT and EPSCSMRT carry `CBL NUMPROC(MIG)`, and the estate's build JCL
    (`Migration/jclToZBuilder/samples/BLDMORT.jcl`) compiles them with `IGY.V6R1M0.SIGYCOMP`, Enterprise COBOL 6.1.
    `mortgage-mpmt` states it. Its proof still waits on C6, not on NUMPROC.
- **NUMPROC(PFD): MATCHED with preferred signs, REFUSED otherwise.** Under PFD "the compiler assumes that the sign in
  your data is one of three preferred signs": C signed positive or zero, D signed negative, F unsigned; "the compiler
  uses whatever sign it is given to process data. The preferred sign is generated only where necessary". NOPFD
  "accepts any valid sign configuration. The preferred sign is always generated in the receiver" (6.4 Programming
  Guide, SC27-8714-03, "Sign representation of zoned and packed-decimal data"). With preferred signs in every value
  read, the two compute the same, so:
  - the oracle compiles PFD as GnuCOBOL's own sign processing (no flag);
  - each det entry point runs with its program's NUMPROC (`Cobol.swapNumprocPfd`, the caller's restored, as TRUNC);
    under PFD the runtime reads a zoned or packed value only with a preferred sign and stops by name ("NUMPROC(PFD):
    ... non-preferred sign ... is not modelled") on any other: F in a signed item, C or D in an unsigned one, D on
    zero. The class test of a signed item with an F sign stops too: Table 7 (NUMCLS(PRIM)) takes C, D, F under NOPFD
    and C, D, "+0" under PFD;
  - a PFD program is proven only through a det port (`equivalence_common.numproc_guard`): a model port or the
    generated service has no such guard and is refused.
  - GnuCOBOL leaves an F sign in a signed item after VALUE ZERO and INITIALIZE (C10) where z/OS writes C, so a PFD
    program that reads one is refused, never misjudged.
  - **Reached.** No case compiles with PFD. Pinned by `tests/cobol_mainframe/test_numproc.py`.
- **TRUNC(OPT): MODELLED (#4706), as C1 describes.** IBM defines OPT's result only for binary values that fit their
  PICTURE, and there it is STD's: the oracle compiles `-fbinary-truncate`, the det runtime computes STD and stops by
  name before storing a value past a binary receiver's PICTURE, so a scenario either stays where IBM is defined or
  is not judged. A port without that stop is proven as STD, a declared difference in its evidence record
  (`option_differences`), never as OPT. CBSA's build JCL passes `TRUNC(OPT)` (`etc/install/base/buildjcl/CICS.jcl:7`):
  most of its programs override it with a `TRUNC(STD)` PROCESS card (C1); CUSTCTRL, DELACC and INQACC have none and
  now run under OPT (the estate options file honours the PARM; #4704 slice 1 had applied it as STD, a deviation).
- **REFUSED:** `INTDATE(LILIAN)` and `ARITH(EXTEND)`, from a CBL/PROCESS card or a case's `compiler_options`, stop the
  run (`UnsupportedOption`).
  - `ARITH(EXTEND)` changes only intermediates past 30 digits (31 instead) and float-mode precision (extended instead
    of long). GnuCOBOL caps neither (C2), so the oracle would compute COMPAT and EXTEND the same; a model needs a
    guard on both sides that stops an intermediate past 30 digits.
  - `INTDATE(LILIAN)` is pinned by IBM (day 1 is 15 October 1582 instead of 1 January 1601), and could be modelled
    by the documented offset of the integer-date functions. Dates before 1601 cannot run on GnuCOBOL and would be
    refused. No case needs it yet.

### Compile options: the table (#4706)
One row per option that can change a result: (1) does it change results; (2) can cobc honour it; (3) what the det
port does; (4) otherwise refused by name or a declared difference (#4702: IBM is the reference, GnuCOBOL the
instrument). Rows for the other options of #4706 follow in its later slices.

| option | (1) changes results? | (2) cobc | (3) det port | (4) otherwise | register |
|---|---|---|---|---|---|
| `TRUNC(STD)` (IBM default) | yes: a binary receiver keeps its PICTURE's digits | `-fbinary-truncate` | `Cobol.swapTruncBinary(true)` | -- | C1 |
| `TRUNC(BIN)` | yes: a binary receiver keeps its bytes | `-fnotrunc` | `Cobol.swapTruncBinary(false)` | -- | C1 |
| `TRUNC(OPT)` | only for a binary value past its PICTURE, where IBM's result is unpredictable; conforming values compute as STD | `-fbinary-truncate` (STD: equal for conforming values) | STD, plus `Cobol.swapTruncOpt(true)`: a value past a COMP / COMP-4 / BINARY receiver's PICTURE stops by name ("TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable") | a port without the stop (model, generated) is proven as STD: a declared difference (`option_differences`) | C1, C5 |

### C6. Floating point — MODELLED in the det runtime as HFP (#4271 slice 1); the oracle DIFFERS
- **What z/OS does.** COMP-1 and COMP-2 are IBM hexadecimal floating point (HFP): a sign bit, a 7-bit characteristic
  (the exponent of 16, excess 64) and 6 (COMP-1) or 14 (COMP-2) hexadecimal fraction digits, big-endian: between 21
  and 24 bits of precision for a short item against IEEE single's 24 (z/Architecture Principles of Operation,
  SA22-7832, "Hexadecimal-Floating-Point Number Representation"). "If any operation in an arithmetic expression is
  computed in floating-point arithmetic, the entire expression is computed as if all operands were converted to
  floating point", when "a receiver or operand is COMP-1, COMP-2, external floating point, or a floating-point
  literal" or "an exponent contains decimal places". Under ARITH(COMPAT) "single precision is used if all receivers
  and operands are COMP-1 data items and the expression contains no multiplication or exponentiation operations",
  long otherwise; a comparison is floating point "if either comparand is a floating-point value" (6.4 Programming
  Guide, SC27-8714-03, Appendix A, "Floating-point data and intermediate results"; "Fixed-point contrasted with
  floating-point arithmetic").
- **What the oracle does.** GnuCOBOL stores IEEE binary floats in machine (little-endian) order. It evaluates the
  expression in decimal: each float is read exactly (`cob_decimal_set_double`), each intermediate is truncated by
  ARITHMETIC-OSVS as fixed point (C2), and the result is stored through a truncation to double and a rounding to
  float. It truncates a float MOVEd to a fixed-point item (0.1 COMP-2 to `V9(4)` is 0.0999; IBM rounds: 0.1000).
  Measured on GnuCOBOL 3.1.2 (2026-10-06): `COMPUTE L2 = (L1 - N3) / N4` gives 0, `COMPUTE L2 = L1 / N4 + S1 * 2`
  drops the second term, and `IF S1 + 1 > 2` is false for S1 = 6.25 -- a float expression with a multiplication,
  a parenthesised division or in a comparison is not decided by the oracle at all.
- **The det runtime (since #4271 slice 1)** models HFP: `cobolrt/Hfp.java`, the translator's own model
  `det/hfp.py`.
  - Storage: `Field.hfp`, the bytes as z/OS holds them; a VALUE is encoded at translation (`layout._put_value`).
  - Arithmetic (`Hfp.add / subtract / multiply / divide`): ADD / SUBTRACT NORMALIZED with one hexadecimal guard
    digit, then normalized and truncated; MULTIPLY and DIVIDE truncate the exact result (Principles of Operation,
    "Hexadecimal-Floating-Point Instructions"). The translator picks each statement's mode by IBM's rule: fixed point,
    short (all COMP-1, no multiplication) or long, every operand converted.
  - Conversions: a COMP-2 to a COMP-1 is rounded (LOAD ROUNDED: IBM, "if a USAGE COMP-2 data item is moved to a
    USAGE COMP-1 data item, rounding occurs"); a float to a fixed-point or numeric-edited item is rounded in the
    receiver's low-order position, with at most 9 (COMP-1) or 18 (COMP-2) significant digits (6.4 Programming
    Guide, "Conversions and precision"). Comparisons are long, unless both comparands are COMP-1.
  - DISPLAY: "A COMP-1 item will display as if it had an external floating-point PICTURE clause of -.9(8)E-99"
    (COMP-2: -.9(17)E-99; 6.4 Language Reference, DISPLAY statement): ` .12500000E 02`.
  - **FUNCTION NUMVAL / NUMVAL-C in a floating-point expression (#4270).** "The returned value is a floating-point
    approximation of the numeric value represented by argument-1. The precision of the returned value depends on the
    setting of the ARITH compiler option" (6.4 Language Reference, SC27-8713-03, NUMVAL, p. 605); "NUMVAL, NUMVAL-C
    and NUMVAL-F return long (64-bit) floating-point values in compatibility mode, and return extended-precision
    (128-bit) floating-point values in extended mode" (6.4 Programming Guide, "Converting to numbers (NUMVAL,
    NUMVAL-C, NUMVAL-F)", p. 115). So the det runtime makes NUMVAL a long HFP operand (`Hfp.numval`): the statement
    is long (a function is no COMP-1 item, so never short), a COMP-1 receiver rounds the long result to short, a
    float MOVEd on to fixed point rounds (above). The digits are converted as any fixed-point value (truncated to
    long, ASSUMED below). Refused by name at run time, where IBM describes no result: an argument of more than 18
    digits ("If the ARITH(COMPAT) compiler option is in effect, the total number of digits must not exceed 18",
    Language Reference) and a value of more than 15 digits from its first nonzero one ("At most 15 decimal digits
    can be converted accurately to long-precision floating point ... Otherwise, the result may lose precision in an
    unexpected manner", Programming Guide p. 115). Under ARITH(EXTEND) (the program's PROCESS / CBL cards over the
    estate's PARM, `program.arith_extend`, the resolver TRUNC and NUMPROC use) every floating-point expression is
    refused by name: extended-precision HFP is not modelled. Proven against the oracle by `test_det_programs.py`
    NUMVALF (exact values, CBSA's shapes: a COMP-1 and a COMP-2 receiver, a reference-modified argument, signs, CR,
    NUMVAL-C, zero, two NUMVALs added, a NUMVAL comparand, the compare and MOVE that follow), and by vectors in
    `test_det_hfp.py`. **The oracle DIFFERS** where the value is not exact in IEEE and HFP: GnuCOBOL computes NUMVAL in
    decimal, stores the nearest IEEE float and truncates it on a MOVE to fixed point -- measured on GnuCOBOL 3.1.2
    (2026-10-08): NUMVAL('0.7') into a COMP-1 then MOVEd to `9(4)V99` gives 0.69 (det, as IBM rounds: 0.70), NUMVAL
    ('12.34') into a COMP-2 then to `9(10)V99` 12.33 (det 12.34). A CBSA case through BNK1CAC / BNK1UAC (an interest
    rate into a COMP-1) or BNK1TFN / BNK1CRA (an amount into a COMP-2) agrees with the oracle only for values exact
    in both formats (a binary fraction: 1.5, 2.25, 100.50, 12.75); no case runs them yet.
  - **FUNCTION NUMVAL / NUMVAL-C in a fixed-point COMPUTE or ADD / SUBTRACT / MULTIPLY / DIVIDE (#4741).** IBM
    evaluates it in floating point too: an operand that is "a reference to a numeric intrinsic function results in
    floating-point arithmetic when ... the function is a floating-point function" (6.4 Programming Guide, SC27-8714-03,
    "Floating-point evaluations", p. 62), and NUMVAL / NUMVAL-C return long floating point (the same guide p. 115;
    Language Reference p. 605), so `COMPUTE B = FUNCTION NUMVAL(A)` with B fixed point (IBM's own example, p. 115)
    is a long-HFP statement. The det translator now makes any arithmetic statement with a NUMVAL / NUMVAL-C operand
    a long one (`float_mode`), the operand `Hfp.numval` with the same run-time refusals as above (more than 18
    digits; more than 15 significant digits). The store of the float result into a fixed-point receiver is
    `Hfp.fixedStore`: **IBM documents the float-to-fixed MOVE (rounded in the low-order position, "Conversions and
    precision") but not an arithmetic statement's store.** The model ASSUMES the store follows that rule: rounded half
    away from zero to the receiver's scale, with or without ROUNDED (ASSUMED, pending z/OS calibration, #4702 part 2).
    So `NUMVAL('0.10')`, 0.0999... in long HFP (`4019999999999999`), stores 0.10 and 123.45 stores 123.45. The
    refusals (more than 18 digits, more than 15 significant digits) and ARITH(EXTEND)'s stand. Proven against
    GnuCOBOL by `test_det_programs.py` NUMVALX (values whose rounded long-HFP value is the oracle's decimal, in byte,
    typed and typed-groups modes) and by `test_det_hfp.py`. The port never follows the oracle: **the oracle DIFFERS**
    where the argument has more decimals than the receiver (GnuCOBOL truncates the exact decimal, the model rounds)
    and for a NUMVAL of more than 15 digits (a 16-digit card number), refused where GnuCOBOL answers.
    **Still exact decimal, as the oracle computes it, though IBM evaluates them in
    floating point too:** NUMVAL in a comparison, in a MOVE, in a subscript, in another function's argument
    (`INTEGER(NUMVAL(X))`), and NUMVAL-F (not translated). **Under ARITH(EXTEND)** a fixed-point statement with a
    NUMVAL operand is refused with the other floating-point expressions.
  - **ASSUMED** (IBM does not document them): a fixed-point value converted to float is truncated to long (then
    rounded to short for a COMP-1); the mantissa of DISPLAY is rounded half away from zero; an arithmetic statement
    that stores a float result in a fixed-point receiver truncates unless ROUNDED (the COBOL rule; except a NUMVAL-only
    statement, which rounds, #4741 above), and a statement
    with several receivers is one mode for all of them.
- **How it is proven** (the oracle cannot run HFP):
  - the byte layout and the arithmetic by hand-computed vectors from IBM's examples (1.0 = `41100000`, -118.625 =
    `C276A000`, 0.1 = `4019999A`, the range ends `7FFFFFFF` / `00100000`, "1 - 16**-8 = 1" through the guard
    digit), and the runtime against `det/hfp.py` bit for bit over a vector table (`test_det_hfp.py`);
  - the behaviour against GnuCOBOL where both formats are exact (`test_det_programs.py` FLOAT, in byte, typed and
    typed-groups modes): every MOVE direction, the four verbs with and without GIVING, COMPUTE, IF / 88 / EVALUATE
    / sign conditions, SET TO TRUE, PERFORM VARYING, INITIALIZE of a group holding a float.
- **REFUSED by name** (a Hole: "... IBM hexadecimal floating point on z/OS, IEEE on the oracle:
  oracle_assumptions.md C6"): a float's bytes or those of an item over it (a group MOVE, a REDEFINES, a reference
  modification, STRING, a CALL argument, a record written, a COMMAREA); a float MOVEd to or from a nonnumeric item;
  a comparison with a nonnumeric operand; exponentiation in a floating-point expression (a run-time routine IBM does
  not document bit for bit); an intrinsic function in one but NUMVAL / NUMVAL-C (IBM's floating-point functions);
  any floating-point expression under ARITH(EXTEND); ON SIZE ERROR and ROUNDED into a float, DIVIDE ... REMAINDER
  in floating point. In the runtime: an HFP exponent overflow or underflow (what z/OS does depends on the program
  mask and Language Environment), a NUMVAL argument past 18 digits or 15 significant ones. `ggdisplay.c` still
  refuses the DISPLAY of a float on the COBOL side (C8), so no proof compares one.
- **Waiting on it.**
  - `mortgage-mpmt` (EPSMPMT): its interest rate is now computed in long HFP, but the payment's `(1 + C) ** N`, N
    with decimal places, is a floating-point exponentiation: the one hole, so the case stays in the det sweep's
    baseline (KNOWN_UNPROVEN). It would also round where GnuCOBOL truncates.
  - CBSA's CRECUST, BANKDATA, BNK1CAC, BNK1CRA, BNK1TFN and BNK1UAC are not cases. Since #4270's NUMVAL slice
    BNK1CAC, BNK1TFN and BNK1UAC translate whole (BNK1CRA still has EXEC CICS INQUIRE).
- **What would settle it.** A z/OS run of EPSMPMT's scenarios (#4050): the exponentiation, and the ASSUMED
  conversions above, checked where the oracle cannot.
- **Later slices of #4271** (left as they are): `NUMPROC(PFD)` with non-preferred signs (refused by name, C5),
  `ARITH(EXTEND)` and `INTDATE(LILIAN)` (detected from CBL / PROCESS cards and refused, C5), COMP-5's
  z/OS byte order where bytes are observable (C7).

### C7. COMP-5 byte order — DIFFERS
- **What.** GnuCOBOL stores COMP-5 in the machine's order, little-endian on x86; z/OS is big-endian. COMP, COMP-4
  and BINARY are big-endian on both.
- **Visible only** when a COMP-5 item's bytes are read as bytes: a REDEFINES, a group MOVE, or a record written to a
  file.
- **Reached.** The harness's SQLCA declares its binary fields COMP-5, as IBM's does, and programs read them only as
  numbers. In the corpora, only CardDemo's IMSFUNCS.cpy declares COMP-5.
- **A VALUE beyond the PICTURE (#4501, fixed).** COMP-5 holds up to its 2, 4 or 8 bytes' capacity, not the value
  its 9s imply. The det translator wrote a COMP-5 VALUE truncated to the PICTURE and big-endian while its runtime
  reads COMP-5 little-endian: `S9(4) COMP-5 VALUE 32767` read back as -12534 (cics-crucible `ca-xctl-versions`,
  XCTL LENGTH). The image now holds the whole value in the runtime's (GnuCOBOL's) order; pinned by
  `test_det_programs.py` COMP5 against GnuCOBOL.
- **Its size** for 1 or 2 digits differs too: C16.

### C8. DISPLAY text — MATCHED
- **What.** GnuCOBOL writes a signed zoned item as `012-` and a binary item as `-00007`. IBM writes their external
  decimal form with the sign overpunched (`01K`, `000P`). `ggdisplay.c` (LD_PRELOAD) rewrites each such operand as
  IBM does.
- **Refused.** An operand outside the model (floating point, more than 32 operands) writes `GGDISPLAY-NOT-MODELLED`,
  and that run's SYSOUT is not compared.

### C9. POINTER size — DIFFERS
- **What.** A POINTER is 8 bytes in GnuCOBOL on x86-64 and 4 on z/OS (31-bit), so every offset after one differs.
- **No oracle setting.** cobc 3.1.2 (the pinned image) lays a POINTER out as the build's `sizeof(void *)`: `cobc
  --info` says `64bit-mode: yes`, no option or configuration key changes the width (`numeric-pointer` makes it
  BINARY-DOUBLE UNSIGNED, still 8; `-fbinary-size` is for PICTURE binary items only). Only a 32-bit (i386) build of
  GnuCOBOL would lay it out in 4 -- a different oracle image, not a flag.
- **Declared, compared by name** (#4270). Each side reads the fields where its own program put them, and they are
  compared by NAME, never as raw bytes across the two layouts:
  - the det port's storage is the oracle's (8-byte POINTER). The generated COMMAREA DTO carries IBM's offsets (4-byte);
    its codec places each field past the wider POINTERs before it (`det.cics.Dto.at`), so the data after a POINTER
    is the same field on both sides, and a DTO whose OCCURS fields appear once carries its whole record (CBSA's
    INQACCCU-COMMAREA: 1981 bytes on z/OS, 1985 here, every account). A POINTER under an OCCURS (wider once per
    occurrence, which the DTO cannot say) is refused by name.
  - the harness lays a record out as the oracle stores it (`equivalence_common.layout_fields`: a POINTER 8 bytes) and
    compares a POINTER only as NULL or not: a scenario can give only `"NULL"` (an address is refused), NULL decodes as
    absent (the det DTO's null), and an address never compares equal -- it is not portable, and IBM gives it no
    stable value. A COMMAREA's EIBCALEN is the oracle's length (INQACCCU 1985, INQACC 107), not z/OS's.
  The port carries a POINTER in a COMMAREA DTO as NULL only (DetCics.pointerIn / pointerOut stop by name on an
  address). Pinned by `tests/cobol_mainframe/test_pointer_commarea_4270.py` (with `EQUIVALENCE_E2E=1`, the oracle's
  bytes against the harness's layout and the det port's storage).
- **Reach.** CBSA passes IMS-era PCB pointers in its COMMAREAs, always NULL: trailing (INQACC, INQCUST, DELACC) and
  with data after one (INQACCCU-COMMAREA, passed by BNK1CCA, CREACC and DELCUS).
- **NULL and pointer-to-pointer SET** (#4270): `SET pointer TO NULL` stores binary zeros over the pointer's bytes --
  GnuCOBOL's NULL is a zero `void *` (8 bytes), and IBM documents NULL as the value that holds no address (Enterprise
  COBOL Language Reference, "Figurative constants": NULL / NULLS; SET statement, format 5 "data-pointer") and sets
  it as X'00000000' (4 bytes), so the bytes are zero on both and only the width differs, as above. `SET p TO q`
  copies q's bytes into p, as both compilers copy the address. CBSA's CREACC (`SET COMM-PCB-POINTER TO NULL`) and
  DELCUS (`SET COMM-PCB-POINTER OF INQACCCU-COMMAREA TO DELACC-COMM-PCB1`). Every other use of NULL -- a comparison,
  a MOVE, a VALUE -- and `SET ADDRESS OF` on a pointer that is read stay refused by name.
- **Procedure and function pointers** (#4462): the det translator lays out USAGE PROCEDURE-POINTER and
  FUNCTION-POINTER as it lays out POINTER, 8 bytes (GnuCOBOL's `sizeof(void *)` for both). IBM's procedure pointer
  is 8 bytes and its function pointer 4 (Enterprise COBOL Language Reference, USAGE clause), so offsets after a
  FUNCTION-POINTER differ the way they do after a POINTER. What is set into either (SET ... TO ENTRY) and a CALL
  through one are not modelled.

### C10. Zoned signs written by INITIALIZE and VALUE ZERO — DIFFERS (tolerated where declared)
- **What.** GnuCOBOL's INITIALIZE and VALUE ZERO leave a signed zoned item's last byte with the unsigned `F` zone;
  Enterprise COBOL writes the preferred sign, `C`. Both are the same positive value; the bytes differ.
- **Where it shows.** CardDemo's CBACT01C writes ARRYFILE entries that INITIALIZE leaves untouched.
- **Tolerance, scoped.** A case lists the datasets it applies to in `"zoned_sign_equivalent"` (only
  `carddemo-readacct`'s ARRYFILE today). In those datasets, and only there, a byte is taken as equal when it is a
  plain digit on one side and the same digit with the positive overpunch on the other (`{`, `A`–`I`: the ASCII
  data's form of an F zone against a C zone; `equivalence.accept_unsigned_positive`). The check is by byte value,
  not by field position, which is why it is declared per dataset rather than applied everywhere. Every such byte is
  counted in the run's summary (`C10: ARRYFILE n sign bytes F/C`), so the tolerance is visible, never silent.
  Everywhere else, signs are compared byte for byte.
- **Not tolerated.** A negative overpunch (`}`, `J`–`R`) against either form, a different digit, or any byte in an
  undeclared dataset.

### C11. A non-digit in a numeric DISPLAY item — DIFFERS (inputs kept out of the cases); as a MOVE sender, an operand and a comparand MODELLED
- **What.** COMEN01C moves the typed option (`WS-OPTION-X`, PIC X(2) JUST RIGHT) to `WS-OPTION` (PIC 9(2)) and then
  tests `WS-OPTION IS NOT NUMERIC`. With a non-digit typed, GnuCOBOL 3 (`-std=ibm`) gives `1!` -> `01` and `!1` ->
  `00`, both NUMERIC (measured 2026-10-03), so `1!` is option 1 and XCTLs. IBM treats an alphanumeric sender of a
  numeric MOVE as an unsigned integer and moves its bytes; a non-digit's digit nibble (`!` is X'5A') is not a digit,
  so on z/OS the item is not NUMERIC and the menu says the option is invalid -- IBM documents no result for such
  data.
- **Found by.** The test-strengthening loop (#4049): the model-written port treats `1!` and `!1` as invalid options,
  GnuCOBOL does not; the proofs differ on both inputs.
- **Now.** Those inputs are not in the case, so the three COMEN01C survivors in the port's own digit test stay case
  gaps. A z/OS run (#4050) settles which side is right.
- **To a binary item (#4652) -- MODELLED, the oracle's arithmetic.** GenApp LGTESTP4's add leaves CA-BROKERID PIC
  9(10) / CA-PAYMENT PIC 9(6) as spaces (INITIALIZE skips the REDEFINES that holds them), and LGAPDB01 MOVEs them to
  S9(9) COMP host variables. GnuCOBOL 3.1.2 (`cob_move_display_to_binary`) counts each byte as its character minus
  '0' -- a space is -16, `A` 17 -- in an unsigned 64-bit integer that wraps, aligns the sender's digits on the
  receiver's decimal places, keeps the receiver's digits under TRUNC(STD) (`val mod 10^digits`; not COMP-5), then
  applies the sender's sign if the receiver is signed: BROKERID 931773840, PAYMENT 707773840 (TRUNC(BIN): the low
  bytes, -597908592). A space where a signed sender's sign is counts -16 and positive, and the oracle then rewrites a
  positive sender's sign byte as an overpunch (a space `{`, a separate space sign `+`). On z/OS a zoned item of
  EBCDIC spaces (X'40') has digit nibbles 0, so the result is most likely 0, but IBM documents no result for
  non-digit data in a numeric item, and the data here is the program's own (not an input a case can leave out). So
  the det runtime models the oracle (`Cobol.nonDigitToBinary`, tested against GnuCOBOL in
  `test_det_nondigit_binary.py`), and genapp-lgtestp4's successful add is proven against it: the proof says the port
  computes what GnuCOBOL computes for these bytes, not what z/OS would INSERT. A signed sender whose sign byte is
  neither a digit, a sign nor a space (`!` the oracle reads as +1, X'FF' as +0) is refused by name.
- **The rest of C11 (#4662) -- MODELLED, the oracle's rules, per shape.** IBM documents no result for non-digit data
  in a numeric item either; each shape below was measured against cobc 3.1.2 (`-std=ibm -fsign=EBCDIC`, TRUNC(STD) and
  TRUNC(BIN)) over unsigned, SIGN TRAILING / LEADING and SIGN TRAILING / LEADING SEPARATE senders holding spaces, letters,
  low-values, X'FF' and `!` in digit and sign positions (`cobolrt/Zoned.java`; `test_det_nondigit_zoned.py`, with the
  expected lines in `nondigit_zoned_expected.txt` and a Docker check that they are still cobc's):

  | Shape | libcob | What the det runtime does |
  |---|---|---|
  | The sign byte of a signed sender, on every numeric read | `cob_get_sign` / `cob_put_sign` (the EBCDIC overpunch) | `{` `A`-`I` are +0..+9, `}` `J`-`R` -0..-9, a digit itself, a space stays a space, any other byte is the digit in its low nibble if that is 1-9 else 0 (`!` +1, X'FF' +0). The read then rewrites a positive sign byte as an overpunch (`0123` becomes `012C`, a space or any non-digit `{`) -- on a MOVE from the item whatever the receiver, and on an arithmetic operand; not on a comparison of an unsigned or trailing-sign item. A separate sign is rewritten to `+` / `-` on every read, comparisons too. Digit-only data included: this changes the sender's bytes in a digit-only program too, as the oracle does. |
  | MOVE zoned to zoned (`MOVE 1A3 TO D7`: `00001A3`) | `cob_move_display_to_display`, `store_common_region` | the digit bytes copied aligned on the decimal point, a space or X'00' becoming '0', any other byte kept; the receiver's sign written over its last / first byte (a digit overpunched, any other byte `{` / `}`) |
  | MOVE to numeric-edited (`MOVE A6 TO E7`: 7 spaces) | `cob_move_display_to_edited` | the digit bytes fed to the picture as they are; only a '0' is suppressed, so a space stays a space and `Z(6)9` of spaces is 7 spaces; X'00' stays X'00' |
  | MOVE to packed (COMP-3) | `cob_move_display_to_packed` | a nibble pair is `(hi * 16 + lo) mod 256` of the digits' values (byte - '0'; a space 0), so `12A4` is `01 31 4C`; reading such a packed item back as a number is still the runtime's (nibble above 9 reads as 9; the oracle prints garbage) -- the tests compare it as the COMP-5 number its bytes are |
  | COMPUTE / ADD / SUBTRACT operand (`COMPUTE B9 = A6` 709551600) | `cob_decimal_set_display` | a first byte X'FF' is +10^size and X'00' -10^size; else leading bytes whose low nibble is 0 (zeros, spaces, low-values) are skipped and the rest accumulate as `value * 10 + (byte - '0')` in an unsigned 64-bit integer that wraps (a space -16, `A` 17), the sign applied after. 19 or more digits left after the skipping: refused by name |
  | `ADD x TO y` / `SUBTRACT x FROM y`, x a zoned field of at most 9 digits, y not COMP under TRUNC(STD), no ROUNDED / SIZE ERROR | `cob_add_int (y, cob_get_int (x))` (cobc's `cb_build_optim_add`) | x read as an int: every digit position counts (a space -16), nothing skipped, nothing wrapped at 64 bits. `gen.py` marks these statements (`Cobol.intOperand`), the runtime decides on TRUNC |
  | `IF x = 0`, `IF x > 5`, `IF x < y`, `IS POSITIVE` (`IF A6 = 0` false) | `cob_cmp_numdisp` for an unsigned or trailing-sign item without decimals; `cob_numeric_cmp` through the decimal for a leading or separate sign or decimal places | numdisp: every digit position in a signed 64-bit integer, nothing skipped, a sign byte that is no overpunch (a space too) 0, nothing written back; the decimal: as an arithmetic operand. NUMERIC is unchanged (a space is not numeric). 19 or more digits: refused by name |
  | MOVE to binary | `cob_move_display_to_binary` (#4652) | unchanged, but a sign byte that is no sign (`!`, X'FF') is no longer refused: it reads as above; a SEPARATE sign other than + - space is still refused |

  IBM has no result for any of these (a zoned item with a digit nibble above 9 or a zone that is no sign is not NUMERIC;
  its use in arithmetic or a MOVE is undefined), and on z/OS a space is X'40', whose digit nibble 0 most likely reads as
  0: the proofs say the port computes what GnuCOBOL computes for these bytes, not what z/OS would. Not modelled, so
  still different or untested: a zoned item with a P position (the digit position count differs, refused by name on
  the MOVE paths), ADD / SUBTRACT / MOVE where the *receiver* holds the non-digit (`ADD 1 TO counter` with spaces:
  `cob_display_add_int` works on the bytes), DISPLAY of a byte above X'7F' (the port writes UTF-8, the oracle the
  byte), a hex literal naming a line-end character in a MOVE (`X'0A'`, `X'0D'`: the generated Java string breaks).

### C12. FUNCTION RANDOM — the numbers DIFFER from z/OS, the interface ASSUMED; refused where IBM does not allow the seed
- **IBM** (Enterprise COBOL 6.4 Language Reference, RANDOM,
  https://www.ibm.com/docs/en/cobol-zos/6.4.0?topic=functions-random): argument-1, if given, "must be zero or a
  positive integer", and only 0 to 2,147,483,645 "yield a distinct sequence"; "if the first reference to this function
  in the run unit does not specify argument-1, the seed value used will be zero"; later references with no argument
  "return the next number in the current sequence"; the value is "exclusively between zero and one". The generator
  itself is not published: the same seed gives z/OS's sequence, which nobody outside IBM can reproduce.
- **The oracle.** GnuCOBOL 3.1.2 (`libcob/intrinsic.c`, `cob_intr_random`) calls glibc's `srand(seed)` (a negative
  seed is 0; glibc makes seed 0 seed 1, so an unseeded process starts as seed 0) and returns `rand() / RAND_MAX` as a
  double, which a COMPUTE takes at its exact binary value. The state is the process's: a CICS task (one process in
  the stub, #4004) shares it across LINK levels.
- **The det runtime** (`Funcs.Random`) reproduces that sequence exactly (glibc's TYPE_3 generator: seeding by
  16807 LCG, 310 numbers discarded) and its double. One sequence per translated program, reset by each entry point
  (`runProgram`, `runBatch`, `runTask`: a run unit begins; IBM's seed zero). A seed that is negative or not an
  integer (IBM does not allow it) or past 2,147,483,647 (the oracle's `cob_get_int`) is refused at run time
  (`IllegalArgumentException`, "not modelled"), never guessed.
- **So a proof says:** given the numbers the oracle draws for the run's seed, the port does what the COBOL does with
  them -- the arithmetic, its truncation into the receiving item, and every output computed from it. It does NOT say
  the port draws z/OS's numbers: a credit score (CBSA CRDTAGY1-5), a customer number (INQCUST, GenApp LGICVS01) or a
  DELAY interval computed from RANDOM differs from z/OS's for the same seed, and is equal across the two sides only
  because both use the oracle's generator. That equality is a stated fact of the harness run, as the clock is (M4):
  the seed these programs use is `EIBTASKN`, which the harness states on both sides (X21: 0 unless a case or scenario
  states its `"taskn"`), so every task draws RANDOM(0)'s sequence by default, and RANDOM(n)'s for a stated n.
- **Known differences, unreached.** The oracle can return exactly 0 or 1 (`rand()` of 0 or `RAND_MAX`, about once in
  2^31 draws), IBM never does; the port follows the oracle. A LINKed program is a new run unit on z/OS (its own
  sequence from seed zero) but shares the task's process state in the oracle; the port gives each program its own
  sequence, so a task whose caller and LINK target both draw unseeded numbers would differ. A CALLed program shares
  its caller's run unit on z/OS; the port keeps the CALLed program's own sequence. No translated program reaches
  these: each one's first reference is seeded.
- **Reached.** No proof yet: no equivalence or crucible case runs CRDTAGY1-5, INQCUST or LGICVS01. Pinned against
  GnuCOBOL by `tests/cobol_mainframe/test_det_programs.py` (`RANDOM`: an unseeded first reference, seeds 0,
  42, 1,234,567 and 2,147,483,647, CRDTAGY's and LGICVS01's COMPUTEs) and against glibc's own numbers by
  `test_det_funcs.py`.
- **To settle.** Only a z/OS run can give IBM's numbers; even then they would be data for a declared difference, not
  a model, since the generator is unpublished.

### C13. A numeric operand compared with a nonnumeric one — MATCHED where IBM and the oracle agree, REFUSED where they do not (#4665)
- **IBM** (Enterprise COBOL 6.4 Language Reference, relation conditions, "Comparison of numeric and alphanumeric
  operands"; the IBM page could not be re-read when this entry was written, so the rule is ASSUMED from it): a
  numeric-edited item belongs to the alphanumeric class, so a numeric-edited item compared with a number is a
  nonnumeric comparison, as an alphanumeric or alphabetic item is. The numeric operand is compared as though it were
  moved to an alphanumeric item of as many characters as its digits -- a MOVE that keeps no sign -- then character
  by character, the shorter operand padded with spaces. The numeric operand must be an integer; IBM rejects a
  non-integer literal or item there.
- **The oracle** (GnuCOBOL 3.1.2 `-std=ibm`, measured 2026-10-07 with `test_det_programs` probes): `E PIC
  ZZZ,ZZ9.99` holding 1500 (`  1,500.00`) is neither greater than `1499.99` nor `1499` -- text, not value. A literal
  is its characters as written: `0012` is `0012`, `12` is `12` (`  12` = `12` is false), `1499.99` is `149999`,
  `0.12` is `012`. A zoned item is its bytes with an overpunched sign unpunched; a packed or binary item its value in
  its PICTURE's digits (`S9(4) COMP-3` 12 is `0012`); the sign is dropped (-1234 equals `1234`). ZERO against an
  edited item is a run of `0` characters. EVALUATE subjects, THRU ranges and an 88 on an edited item compare the
  same way.
- **Where they differ.** A signed literal: the oracle compares its sign character (`+1234` equals `+1234`, not
  `1234`), IBM moves no sign. A SIGN SEPARATE item: the oracle compares its sign character (`-1234`), IBM drops it.
  A P-scaled item: the oracle compares its stored digits (`99PP` holding 1200 is `12`), IBM's characters are not
  settled. An arithmetic expression against a nonnumeric item: the oracle compares its result as text of its own
  making (`  12` is not `10 + 2`, `1234` is `1000 + 234`), IBM documents no such comparison. A non-integer literal or
  item: IBM rejects the program; the oracle's digits (point dropped) are modelled, since a program IBM compiles
  never reaches them -- except an equality (`=`, `NOT =`, an EVALUATE WHEN, an 88 VALUE) of a numeric-edited item
  with a literal of more decimal places than the item's: cobc decides it when it compiles (`ZZ9` holding 125 is not
  `= 12.5` and `NOT = 12.5`, yet neither `< 12.5` nor `> 12.5`; `Z99V9` holding 112.5 is `= 112.5`, not `= 11.25`),
  so it is refused (measured 2026-10-08). A signed literal against an alphanumeric item is the same: `'12'` is not
  `+12` nor `-12`, `'+12'` is `+12`, `'-12'` is `-12` (measured 2026-10-08).
- **The det port.** The generator passes a numeric literal against a nonnumeric item as its written characters
  (`expr.NumLit` keeps the spelling; `Gen.literal_text`), the runtime (`Cobol.compare(Field, Field)`) compares a
  numeric item against an elementary nonnumeric one as its digits; the five differing shapes are holes by name
  ("... (C13)"). A group against a numeric item is unchanged (its bytes; not measured here).
- **Pinned** by `tests/cobol_mainframe/test_det_programs.py` (`EDCMP` against GnuCOBOL; the refusals by name).
- **To settle.** A z/OS run of `EDCMP` (and of a signed-literal variant) would confirm IBM's characters.

### C14. Size errors (a zero divisor, an exponent, overflow) — the det runtime MATCHES the oracle (#4655); the oracle DIFFERS from z/OS where IBM leaves the result undefined
- **IBM** (Enterprise COBOL for z/OS Language Reference, "SIZE ERROR phrases"; the wording below is paraphrased
  from the 6.x manual and not re-fetched for this entry -- confirm it against
  https://www.ibm.com/docs/en/cobol-zos/6.4.0?topic=statements-size-error-phrases before quoting it): a size error
  condition is a result whose absolute value, after decimal-point alignment, exceeds the receiver; a division by
  zero; and, in an exponentiation, zero raised to the zero power, zero raised to a negative power, or a negative
  number raised to a fractional power. It applies to final results only. With ON SIZE ERROR the receivers keep
  their values and the imperative statement runs. Without it, an overflow is truncated (the receiver's high-order
  digits are lost) and the result of the other cases is undefined; on z/OS a packed-decimal divide by zero is a
  decimal-divide exception (S0CB abend) unless the compiler checks first.
- **The oracle** (GnuCOBOL 3.1.2 `-std=ibm`, measured 2026-10-07): a zero divisor makes libcob's NaN intermediate
  (`cob_decimal_div` sets scale COB_DECIMAL_NAN and EC-SIZE-ZERO-DIVIDE); an operation with a NaN operand gives NaN;
  storing a NaN (`cob_decimal_get_field`) leaves the receiver unchanged. So, with or without ON SIZE ERROR:
  `COMPUTE R R2 = A / Z` changes neither receiver; `COMPUTE R = A / Z + 1` and `(A / Z) * 0 + 7` change nothing;
  `DIVIDE Z INTO R R2` leaves each receiver; `DIVIDE A BY Z GIVING Q REMAINDER RM` leaves Q and RM; `0 / 0` is the
  same. Where cobc truncates an intermediate (ARITHMETIC-OSVS, C2), `cob_decimal_align` turns the NaN into 0:
  `COMPUTE R = A / Z * C` stores 0, and `(A / Z) + (A / B)` stores A / B; in a condition an aligned quotient is 0
  (`A / Z = 0` is true) while an unaligned one compares as its dividend scaled by 10^32768 (`0 = A / Z` is false).
  An intrinsic function's argument divided by zero is 0 (`cob_intr_binop`), and FUNCTION MOD / REM by zero are 0
  with no size error. `0 ** 0` is 1 with the size error raised; `0 ** -1` is 0 with no size error; a negative base
  with a fractional exponent, or an exponent past a double's range, leaves the receiver unchanged with the size
  error raised. An overflow without ON SIZE ERROR is truncated (IBM's rule). With ON SIZE ERROR the phrase runs
  whenever the statement raised a size error, even if a receiver changed (the aligned 0, 0 ** 0's 1); the
  exception code is cleared when the statement starts.
- **The det runtime (since #4655)** does the same: `Cobol.divide` returns libcob's NaN (the dividend's digits at
  scale -32768) for a zero divisor, `Cobol.add / subtract / multiply / negate / power` carry it where the translator
  sees that an operand can be one (a division or an exponent below it), `Cobol.store` and `storeChecked` leave the
  receiver (a lifted receiver is guarded with `Cobol.isNan`), `Cobol.align` truncates it to 0 as libcob does, and a
  comparison sees its scaled value as cob_decimal_cmp does. A division inside a function's argument is
  `Cobol.divideIntr` (0). A statement with ON SIZE ERROR and a division or exponent clears and reads the size-error
  state (`Cobol.sizeClear` / `sizeRaised`, per thread). `Cobol.remainder` computes DIVIDE's REMAINDER from the
  quotient truncated to the quotient receiver's places, as cob_div_quotient does (before, the stored quotient was
  used: a quotient too big for its receiver, or ROUNDED up, gave a wrong remainder). Pinned by
  `tests/cobol_mainframe/test_det_size_error.py` (every shape above, both port modes) and a randomized differential
  run (2026-10-07: 56 random programs with zero divisors, DIVIDE and ON SIZE ERROR / NOT ON SIZE ERROR phrases,
  every output equal to the oracle's).
- **Floating point (#4675).** The oracle converts a COMP-1 / COMP-2 operand to a decimal, so a zero divisor behaves
  as above (measured 2026-10-08): `COMPUTE G = F / FZ`, `DIVIDE FZ INTO G`, `DIVIDE F BY FZ GIVING G` (or a decimal
  receiver) leave every receiver unchanged and raise the size error, with or without ON SIZE ERROR; ON SIZE ERROR
  also fires for a decimal receiver too small for a float result (`R = F * 3000`). The det runtime does the same for
  a division that is the statement's whole value (`Hfp.divide` returns the NaN and raises the size error; the float
  statements now take ON SIZE ERROR phrases, an HFP exponent overflow is still refused by name). A zero divisor
  inside a larger float expression is NOT modelled: the oracle's `cob_decimal_align` meets the NaN there
  (`(F / FZ) * 3` is unchanged but `(F / FZ) * C`, `FM * (F / FZ)` store 0, `2 - (F / FZ)` stores 2) and the HFP model
  does not replay it, so `Hfp.divideNested` stops the run with an ArithmeticException, a named stop rather than a guess.
  z/OS leaves the result of a floating-point zero divide undefined (a floating-point exception or a program-defined
  result), so the oracle's "unchanged" is the same kind of choice as for decimal items.
- **Phrase scope (#4676).** A conditional phrase belongs to the innermost unterminated statement that can take it,
  and an END-verb closes the innermost open statement of its verb (measured: `COMPUTE ... ON SIZE ERROR COMPUTE ...
  NOT ON SIZE ERROR ...` gives the NOT phrase to the inner COMPUTE; with an inner ON/NOT pair of its own the next NOT
  goes to the outer). `det/stmt.py` binds them that way (`_phrase_owner`, `_end_owner`). A NOT phrase after a
  statement that already has one, or after a finished one, goes outward; cobc rejects a stray one with a syntax error.
- **So a proof says:** for a scenario that divides by zero without ON SIZE ERROR, the port does what the oracle
  does (receivers unchanged), which z/OS does not promise: IBM leaves the result undefined and a z/OS run may
  abend. With ON SIZE ERROR both sides agree with IBM (receivers unchanged, the phrase runs), except `0 ** -n`,
  which IBM calls a size error and the oracle (and so the port) computes as 0.
- **Reached.** Not known to be: no proven scenario divides by zero or raises a size error from an exponent.
- **To settle.** A z/OS run of the shapes in `test_det_size_error.py` without ON SIZE ERROR.

### C15. CALL identifier — the program is the item's content: MODELLED over the names the source fixes, REFUSED otherwise (#4736)
- **IBM** (Enterprise COBOL for z/OS 6.4 Language Reference, CALL statement,
  https://www.ibm.com/docs/en/cobol-zos/6.4.0?topic=statements-call-statement, read 2026-10-09): identifier-1 "must be
  an alphanumeric, alphabetic, or numeric data item described with USAGE DISPLAY"; "literal-1 or the contents of
  identifier-1 must specify the program-name of the called subprogram"; "the rules of formation for program-names are
  dependent on the PGMNAME compiler option". An exception condition occurs "when the called subprogram cannot be made
  available": ON EXCEPTION (ON OVERFLOW, the same) runs its imperative statement, and NOT ON EXCEPTION is ignored when
  no ON EXCEPTION is written. The page does not say what ends the run unit without the phrase, whether the name's
  case or trailing blanks matter, or what a name longer than eight characters does (the PROGRAM-ID rules and the
  PGMNAME option decide).
- **The port** (`det/dyncall.py`, `Gen.dynamic_call`). The names the item can hold when the CALL runs are found from
  the source: (1) a MOVE of a literal, or of an item whose bytes VALUE clauses fix and nothing writes (through a
  REDEFINES table too: DBB EPSCSMRT's `MOVE CALLED-PROGRAM-NAME(1) TO WS-CALLED-PROGRAM`, subscripts literal),
  earlier in the CALL's paragraph on its own path with nothing between that may write the item; else (2) an item with
  a VALUE clause whose every write in the program is such a MOVE: its VALUE and each MOVEd value. One name is one
  call; several are a switch on the item's content (trailing blanks trimmed) with a case per name. Each name is
  checked: an estate service with a CALL entry or a library routine (CEEDAYS, COBDATFT, CEE3ABD), uppercase, at most
  8 characters (PGMNAME(COMPAT)); else the statement is refused by that name. Refused by name too: an item with no
  VALUE, a write the analysis cannot read (a READ INTO, a STRING, a group MOVE, an alias through REDEFINES, the item
  in a CALL's USING list, a MOVE from COMMAREA data, a computed subscript), a blank name, and ON EXCEPTION /
  OVERFLOW phrases. A name no estate program answers to (EPSCSMRT's `'NOT VLD'` entry, never moved) is refused only
  when it can reach the CALL, never for sitting in a table.
- **Not modelled.** What the run unit does when a dynamic CALL finds no program (IBM: not stated on the page above; the
  oracle: a run-time error). The port never reaches that case: every name it can reach is a known program.
  CANCEL is refused by the translator already (an unmodelled verb), so a callee's state is the run unit's.
- **Reached.** Yes: `tests/cobol_mainframe/test_det_dynamic_call_4736.py` runs each shape under GnuCOBOL (callees as
  modules) and as the port (callees' services written by hand) and compares the output. DBB EPSCSMRT translates whole;
  its callee EPSMPMT stays refused (a COMP-1 item, C6), so no equivalence case of EPSCSMRT is possible yet.

### C16. A 1- or 2-digit COMP-5 item — the oracle DIFFERS (one byte), REFUSED by name (#4751)
- **IBM.** Binary items -- COMP, COMP-4, BINARY and COMP-5 alike -- of 1 to 4 digits occupy a halfword (2 bytes), 5
  to 9 a fullword, 10 to 18 a doubleword (Enterprise COBOL for z/OS Language Reference, USAGE clause, "Computational
  items"). COMP-5 holds up to the capacity of those bytes (C7), so `MOVE 99999` to a `PIC S9(2) COMP-5` leaves -31073
  (99999 modulo 2 ** 16, signed). The det layout (`det/layout.py`, `Item.elementary_size`) sizes it so.
- **The oracle.** GnuCOBOL 3.1.2 sizes COMP / COMP-4 / BINARY by its `binary-size` setting, which `-std=ibm` already
  sets to `2-4-8` (`/etc/gnucobol/ibm-strict.conf`; the default dialect's is `1-2-4-8`), but COMP-5 by the PICTURE's
  9s alone: 1 or 2 of them are one byte whatever `-fbinary-size` says (only `1--8` changes COMP-5, and only to pack
  wider items tighter). Measured 2026-10-09 on the pinned image (`cobc -x -std=ibm -fsign=EBCDIC`, alone and with
  `-fbinary-size=2-4-8`, `-fbinary-size=1-2-4-8`, `-fbinary-truncate`, `-fnotrunc`): `LENGTH OF` a `PIC S9(1)`,
  `S9(2)`, `9(2)`, `S9V9` or `9PP` COMP-5 item is 1, also under a group's `USAGE COMP-5`; `S9(3)` and wider are 2,
  4 or 8 as on z/OS; `MOVE 99999` leaves -97, `MOVE 300` to `9(2)` 44; a group of `S9(2) COMP-5`, `S9(2) COMP`,
  `S9(4) COMP-5`, `X` is 6 bytes (z/OS and the det layout: 7). `-fbinary-size=2-4-8` changes no byte.
- **So the oracle refuses it.** `equivalence_common.comp5_layout_guard` scans every COBOL source staged for an
  oracle build -- the program, its copybooks, the programs it calls or links to, a crucible case's programs
  (batch, CALL, CICS and the CICS crucible) -- and refuses the case by name when one declares such an item; a
  proof is never loosened to tolerate the bytes. Pinned by `tests/cobol_mainframe/test_comp5_layout.py` (the
  scanner, the det layout's halfword, and with `EQUIVALENCE_E2E=1` the oracle's one byte: if a new image lays it
  out in a halfword, drop the guard and this entry).
- **Reach.** None: no corpus and no case declares one (CardDemo's IMSFUNCS.cpy, the only COMP-5 in the corpora, is
  `PIC S9(05)`; the harness's SQLCA uses `S9(4)` and `S9(9)`).

## Data and encoding

### D1. Text order is ASCII — DIFFERS
- **What.** Proofs run with ISO-8859-1 data on both sides, so every alphanumeric comparison (`IF A > B`, a THRU range,
  a key's order) uses ASCII order. EBCDIC order differs:
  - lower case sorts before upper case;
  - letters sort before digits;
  - space sorts before both.
- **Keys.** Indexed files are browsed in ASCII order on both sides (`equivalence.COLLATION`). CardDemo's keys sort the
  same either way. Keys mixing letters and digits would not.
- **SORT / MERGE under an alphabet (#4268).** `ALPHABET ... IS EBCDIC` orders by code page 037 on z/OS (the default
  CODEPAGE(1140)'s order); GnuCOBOL uses its own ASCII-to-EBCDIC table, which agrees for every 7-bit character but
  `[ ] ^ |` and for no byte above X'7F'. A literal alphabet's THRU ranges and its unnamed characters follow the
  native set: EBCDIC on z/OS, the data's bytes in GnuCOBOL. The det runtime (`Sort.Collating`) keeps both orders,
  sorts by IBM's, and stops by name on a pair of keys the two order differently, so a proven sort is IBM's. A key
  under an alphabet must hold characters only (a packed or binary byte is the same byte in both code pages).
- **In-program comparisons.** `Cobol.compare` is byte order in the data's code page. No audit has counted the
  relational comparisons whose result could change between ASCII and EBCDIC.
- **PROGRAM COLLATING SEQUENCE in relation conditions (#4539).** Under an EBCDIC or a literal alphabet, the
  nonnumeric comparisons of IF, EVALUATE (conditions and THRU ranges), PERFORM UNTIL and condition-names (88 THRU
  ranges) go through `Sort.Collating` as SORT keys do: the shorter operand padded with spaces, IBM's order taken,
  a pair of operands the two order differently stopped by name. Numeric comparisons stay by value; national data
  is refused by the translator. An equality consults the alphabet only when it has ALSO (otherwise each character
  has a position of its own). Refused by name: HIGH-VALUE / LOW-VALUE under a literal alphabet (the characters of
  its highest / lowest position; GnuCOBOL's LOW-VALUE is the alphabet's first character), an ordering of an item
  holding packed / binary / signed items, and an ordinal alphabet. Under EBCDIC,
  HIGH-VALUE is X'FF' on both sides, but the harness's byte X'FF' is 'ÿ' (cp037 X'DF'): an ordering of HIGH-VALUE
  against a character cp037 places above X'DF' (S-Z, digits) stops the run by name. SEARCH is not translated.
- **A migration decision as much as an oracle gap.** A port that will run on ASCII data either keeps ASCII order (a
  declared difference, #4051) or compares in cp037 order.
- **To settle.**
  1. Count the alphanumeric relational conditions per proven program.
  2. Run the proofs with `data_encoding: cp037` where the program's literals allow it.

### D2. Hex literals that name EBCDIC characters — DIFFERS
- **What.** `X'40'` is a space on z/OS and `@` in ASCII.
- **Corpora.**
  - GenApp's LGTESTC1 uses `x'40'` and `x'00'`; it is not a proven case.
  - CardDemo's CSUTLDTC compares LE feedback tokens (`X'...C3C5C5'`, "CEE" in EBCDIC). The CEEDAYS model writes
    those same bytes.
  - CBSA's PROCTRAN.cpy uses `X'FF'`, which is the same byte in both.
- **Screen attributes.** The DFHBMSCA stand-in holds the EBCDIC byte values, as the program's symbolic map expects
  them.

- **Raw bytes, not characters (#4698).** IBM: a hexadecimal literal `X'hh..'` denotes exactly those bytes, with no
  code-page translation (Enterprise COBOL for z/OS Language Reference, "Hexadecimal notation for alphanumeric
  literals"); an ordinary literal `'...'` is characters, in the code page of the compiler's CODEPAGE option. The port
  keeps that difference under every record charset: `Cobol.hex` gives the text the record charset encodes back to
  the literal's bytes, an ordinary literal is encoded by the charset as before, and a field's bytes (EBCDIC data a
  program read or moved) are shown as the bytes they are. The runtime's record charset keeps all 256 byte values
  (`cobolrt/Lossless`): a byte a single-byte charset leaves unmapped, such as X'81' in windows-1252, is its latin-1
  character and encodes back to that byte. GnuCOBOL writes the same raw bytes.
- **The line separator is framing, not data (#4698).** A DISPLAY to SYSOUT on z/OS writes a record of the item's
  bytes; there is no newline byte. Our SYSOUT capture needs a separator, so the Sysout (batch and standalone) writes a
  plain LF (0x0A, as cobc does) after each DISPLAY in every record charset, not the charset's encoding of `"\n"`
  (0x15 / 0x25 on EBCDIC). The harness compares records: it splits both captures on the LF byte, then decodes each
  record (`equivalence_common.sysout_lines` / `compare_sysout`).

### D3. Zoned signs in ASCII data — MATCHED
- `-fsign=EBCDIC` reads the corpora's ASCII data with EBCDIC-style overpunch (`{` = +0, A–I positive, `}` J–R
  negative), as the data was unloaded from z/OS.

### D4. A character no single-byte code page holds, in an alphanumeric literal — REFUSED (the statement, #4272)
- **What.** A UTF-8 source with an em dash (U+2014) in `MOVE 'Conto bloccato — operazione negata' TO WS-MSG` (a
  census estate's CICS messages, 2026-10-06). Enterprise COBOL reads its source in the single-byte EBCDIC code page
  of its CODEPAGE option, and an alphanumeric literal's length is its bytes in that page (Enterprise COBOL for z/OS
  Language Reference, "Alphanumeric literals"; DBCS characters only as a mixed literal
  between shift-out / shift-in under the DBCS option). No SBCS EBCDIC page (037, 1140, 280 / 1144 ...) and not
  Latin-1, the det runtime's record charset, holds U+2014.
- **Why refused.** COBOL does not decide what the literal is: the transfer of the source to the compiler does. A
  transcoding transfer substitutes one byte (SUB, X'3F') or fails; a binary one keeps three bytes (X'E28094', read as
  EBCDIC characters); GnuCOBOL takes the three UTF-8 bytes as written. The literal's bytes and its length (so the
  receiver's padding or truncation) differ between them; guessing one would make a port agree with one toolchain and
  not the estate's. Even column 72 moves: the translator counts a character a column, a compiler reading the UTF-8
  bytes counts the em dash as three.
- **What the translator does.** `source.narrowed` hands the grammar a stand-in (U+001D) for the character, column
  for column, and the statement holding the literal (a MOVE, an IF's or a WHEN's condition, an EXEC block) is
  `throw new Hole(...)` with gen.WIDE_WHY; the rest of the program translates. The literal never reaches Java.
- **Still refused whole** (`source.unmodelled`): the character in a VALUE (it lays the program's storage out), in a
  national / DBCS literal (N'…', G'…', NX'…', U'…': national data is not modelled, #4272) or in a name. In a `*>`
  comment it is read (no parser reads a comment).
- **To settle.** An estate that states how its source reached the compiler (its transfer code page, or GnuCOBOL with
  UTF-8 source) decides the bytes; then the literal can be translated to them.

## Files

### F1. FILE STATUS from GnuCOBOL's indexed files — ASSUMED
- **What.** The statuses a run meets naturally (00, 02, 10, 22, 23, 35 …) come from GnuCOBOL's Berkeley DB files.
- **Assumed** to match VSAM for these common codes.
- **Not modelled.** VSAM's OPEN-time checks: 39 (attributes conflict), 04 (record length) and 97 (verified open).

### F2. Injected faults — MATCHED
- Fault runs (`ggfault.c`, CICS `faults.cfg`) give a statement the same status or RESP on both sides, and say which
  faults fired.
- The values are the ones IBM documents for the condition. What a real device failure would give is not modelled.
- **CICS commands beyond files (#4049).** XCTL, WRITEQ TS, START, RETRIEVE and CANCEL take a plan too (named by the
  program, queue, TRANSID, `-` and REQID), in the equivalence harness and in the CICS crucible's strengthened
  scenarios. A planned command does nothing but return its RESP / RESP2: the XCTL does not transfer, the WRITEQ TS
  writes no item, the START schedules nothing, the RETRIEVE moves no data, the CANCEL cancels nothing. IBM's
  descriptions of these conditions say the request was not performed; a partial effect is not modelled. Only
  conditions IBM lists for the command are planned (CICS TS, each command's "Conditions"): XCTL PGMIDERR (RESP2 3,
  the program could not be loaded); WRITEQ TS INVREQ; START INVREQ (RESP2 17); RETRIEVE IOERR. An unhandled one
  abends with the code the stub and CicsTask already give it (AEI0, AEIP). CANCEL has no INVREQ, so a port's
  `INVREQ` branch after CANCEL stays unreachable.

### F3. Record formats — ASSUMED
- Most cases' datasets are fixed-length records.
- **Variable-length records (RECFM=VB)** are exercised since `carddemo-readacct` (CBACT01C's VBRCFILE: a 12-byte and
  a 39-byte record per account, `RECORD VARYING DEPENDING ON`). Records are compared by content and length, framed
  as GnuCOBOL writes a variable sequential file: a 2-byte big-endian length, two zero bytes, then the data
  (`equivalence_common.split_varseq`). Unlike a z/OS RDW, that length does not count the 4-byte header.
- **Assumed.** That a record's content and length are what z/OS would write; block descriptors (BDW) and spanned
  records are not modelled. The det translator writes the same framing (`DetFiles`); before this it wrote VB records
  padded to the maximum length, which no case had exercised.

### F4. JCL utility steps — out of scope
- A batch case runs one program step.
- SORT, IDCAMS, IEBGENER and DFSORT steps are not run. The generated batch job refuses a utility step by name
  (`JclSteps.utility`: the job fails on its TODO, or with `gitgalaxy.batch.skip-unimplemented` the step is logged as
  skipped; never a silent success).
  Next slice of #4268: DFSORT / ICETOOL control cards (SORT FIELDS, INCLUDE / OMIT, OUTREC / INREC, SUM), IEBGENER
  and an IDCAMS REPRO / DEFINE subset in the oracle, and a multi-step job case.
- The COBOL SORT / MERGE / RELEASE / RETURN verbs and the SD entry are translated (#4286), onto `cobolrt/Sort`:
  - Keys compare as a relation condition compares their items: a numeric key (zoned, packed, binary, signed or
    not) by value, any other byte by byte. WITH DUPLICATES IN ORDER is a stable sort; without it, records with
    equal keys and different bytes stop the run by name (IBM: their order is undefined). A MERGE input out of key
    order stops the run by name.
  - USING / GIVING files are opened, read or written and closed implicitly; their FILE STATUS items are left as
    they were (GnuCOBOL does not set them; IBM's depends on FASTSRT).
  - COLLATING SEQUENCE (or PROGRAM COLLATING SEQUENCE): NATIVE, STANDARD-1 and STANDARD-2 are the data's byte order
    (D1). EBCDIC and literal alphabets (#4268) order the alphanumeric keys; see D1 for where IBM and GnuCOBOL
    differ.
  - Refused by name: SORT of a table (format 2), a key under OCCURS, an SD whose records differ in length, a USING /
    GIVING file whose records are not the SD record's length, SORT-RETURN set by the program (16 ends a sort), an
    alphabet ordinal (a numeric literal names a native code: EBCDIC on z/OS), HIGH-VALUE / LOW-VALUE in an
    alphabet, and a group key holding numeric items under an alphabet.

## CICS (`ggcics.c`)

### X1. Commands from IBM's documentation — ASSUMED
- **Source.** Each command's RESP/RESP2, length handling and EIB fields follow the IBM CICS TS for z/OS 6.x API
  reference, cited in the code.
- **Checked against.** The cics-crucible (210 doc-cited cells passing, v0.5.0). Not checked against a CICS region.

### X2. Screens are compared as the symbolic map — ASSUMED
- **Compared.** Each SEND MAP's symbolic map: the data, the attribute, colour and highlight subfields, and the cursor
  (length -1).
- **Not modelled.** What a 3270 shows after BMS merges the physical map, MAPONLY, DATAONLY, ERASE and FRSET. Two
  ports with equal symbolic maps could differ on a terminal only if BMS itself differed.

### X3. Backout and recoverable files — MATCHED
- **What.** SYNCPOINT ROLLBACK, or an abend that terminates the task, backs out the unit of work: the recoverable files'
  changes and the task's Db2 changes. A file the CSD defines RECOVERY(NONE) keeps its changes (CBSA's ABNDFILE: the
  abend log a backout must not undo).
- **How.** A case states a dataset's RECOVERY(NONE) (`"recovery": "NONE"`, with a `recovery_why` citing the CSD: the
  engine's facts do not carry the attribute). The COBOL model does not save such a file for backout; the Java side
  makes its changes outside the task's transaction (REQUIRES_NEW).
- **Fixed 2026-10-02.** Until then the COBOL model backed out every file, and the Java side backed out nothing on an
  abend that terminated the task (only on SYNCPOINT ROLLBACK). No proven scenario had changed a file and then abended.
- **Not modelled.** Temporary storage is not backed out (CICS backs out recoverable TS queues).
- **SYNCPOINT's response (#4437).** Both sides answer SYNCPOINT and SYNCPOINT ROLLBACK with NORMAL (RESP 0,
  RESP2 0, EIBRESP too); the det port writes it where it used to leave RESP / RESP2 as they were. IBM documents
  INVREQ (RESP2 200: a program LINKed from a remote system without SYNCONRETURN, or one defined
  EXECUTIONSET(DPLSUBSET)) and, for SYNCPOINT only, ROLLEDBACK (a remote system cannot commit). In the modelled
  region a LINK is local and no remote system takes part. A program LINKed from outside the region (CicsTask's DPL
  server, `LocalRegion.linked`) refuses SYNCPOINT, since the region does not know whether its client gave
  SYNCONRETURN. EXECUTIONSET is not read: CBSA's CSD defines its programs FULLAPI (`BANK.csd`).

### X4. Time — ASSUMED
- **What.** EIBDATE and EIBTIME are the case's clock at dispatch. ASKTIME leaves them unchanged (a task takes no time),
  and FORMATTIME formats from that clock.
- A DELAY takes no time either (CBSA's INQCUST and credit agencies retry after one); ENQ and DEQ are NORMAL, one
  task being the region's only one.

### X5. What IBM leaves open — REFUSED
Refused by name (`equivalence_cics.Unsupported`):
- HANDLE ABEND PROGRAM;
- START with interval options;
- READQ TS with SET or SYSID;
- an option the stub does not know.

The length READQ TS returns on ITEMERR or QIDERR is not documented, so it is not set.

### X6. A WRITEQ LENGTH past its FROM item — REFUSED, the task judged up to it
- **What.** GenApp's LGSTSQ (the error logger every GenApp program LINKs on its error paths) writes
  `LENGTH(WS-RECV-LEN)`, the caller's COMMAREA length + 5. That is more than `FROM(WRITE-MSG)` holds (95 bytes) when the
  caller passes more than 90 bytes -- WRITE-ERROR-MESSAGE's second LINK passes the 99-byte CA-ERROR-MSG, so LGSTSQ
  writes 104 bytes -- and CICS copies the bytes that follow WRITE-MSG in storage.
- **Why the WRITEQ is not judged.** Those bytes depend on how the compiler lays out WORKING-STORAGE; GnuCOBOL's layout
  is not IBM's, so no oracle here can say what z/OS writes. **Not settled on z/OS (#4050).**
- **Refused, both sides.** The translated WRITEQ TD / TS checks its LENGTH against the FROM item and stops the run (98,
  "WRITEQ TD LENGTH > FROM: not modelled"); the det port refuses at the same statement (`DetCics.within` throws
  `DetCics.PastFrom`, #4607). START / PUT CONTAINER / GET CONTAINER past their area stay refused whole.
- **Judged up to the refused WRITEQ** (owner decision on #4607, 2026-10-07). A task that reaches it -- a scenario or a
  derived SQL-fault task -- is compared up to that statement, the way #4173 judges a task up to a LINK not run:
  every event before it (the LINKs, the WRITEQ TD / TS records of the first, short LGSTSQ call, RETURNs) field by
  field, and it passes only when BOTH sides stopped at it (the report's `x6`; `judged_to` names the refusal). Its end
  state -- files, tables, the COMMAREA it leaves -- is not compared. The branch outcomes it ran before the refusal
  count as executed (the COBOL trace stops at the refusal). A proof that leans on such a task lists X6 among its
  assumptions: what the task would have done after the WRITEQ on z/OS is not claimed.
- **#4173.** An SQL-fault task (M2) that reaches a LINK to a program the case does not run is judged up to and
  including that LINK -- its events and the COMMAREA's bytes as LINKed, byte for byte. With LGSTSQ in a case's
  `"programs"` (GenApp's Db2 cases, #4607) the task runs on to the X6 refusal instead.
- **Reached since (#4270, X23):** WRITE-ERROR-MESSAGE's `IF EIBCALEN < 91` true side in LGACDB02, LGDPDB01 and
  LGIPDB01, by scenarios that state a COMMAREA shorter than 91 bytes (`commarea_length`). LGACDB01's and LGUCDB01's
  need a failing statement whose host variables lie past EIBCALEN (X23).

### X7. ASSIGN INVOKINGPROG / PROGRAM, and several programs in one task — MATCHED
- ASSIGN PROGRAM is the running program, INVOKINGPROG the program that LINKed or XCTLed to it (blanks for a task's
  first program), as IBM's ASSIGN documents.
- A case's `"programs"` run in the same task on both sides: the COBOL side's dispatcher (as the cics-crucible's) and
  the Java side's `CicsTask.Programs`, each a port. A LINK is compared by its target; what the target did is compared
  through its files, tables, queue writes and the COMMAREA it leaves.
- **Queue writes (#4607).** A WRITEQ TD is an event (queue, record text) and so is a WRITEQ TS (queue, the item as
  text, RESP, item number), on both sides as CicsTask records them. Before #4607 the COBOL side dropped the stub's
  WRITEQ-TS line, so any task that wrote TS differed. The item is read in each side's page: the stub's storage page,
  and the det port's region page (CCSID 037 by default, #4528); a port in another region page shows as a difference.

### X8. A reference modification past its item — not run
- **What.** GenApp's LGAPDB01 MOVEs into `WS-VARY-CHAR(1:WS-VARY-LEN)`, the COMMAREA's length less the request's:
  with the 32500 bytes its caller LGAPOL01 passes, about 28K past WS-VARY-CHAR's 3900. Compiled without SSRANGE (IBM's
  default) that overwrites whatever follows in storage; GnuCOBOL's layout is not IBM's.
- **Effect.** The det port stops (an index error), so such a scenario can never be proven by accident; the case leaves
  it out and says so. A COBOL-side check (GnuCOBOL's EC-BOUND-REF-MOD) would turn it into a refusal by name.
- **A subscript past its table is the same** (#4463): CardDemo COMEN01C rejects an option above 11, then still reads
  `CDEMO-MENU-OPT-USRTYPE(WS-OPTION)`; option 99 reads 4K past the record. carddemo-menu's `option-12-typed-over` sent
  99 from #4049 on, and its det port stopped there (an index error) -- the case now sends 12, inside the 12-entry
  table. GnuCOBOL's EC-BOUND-SUBSCRIPT would make the COBOL side refuse such a scenario by name.

### X9. Named counters — MATCHED
- GET COUNTER returns the counter's value and then adds one (IBM CICS TS, GET COUNTER); a counter the region does not
  have is INVREQ RESP2 201 (X30: it was NOTFND before; IBM lists none). A case (or a scenario) states the region's counters (`"counters": {"POOL/NAME": next}`); both sides
  read the same. Other counter options (INCREMENT, WRAP, MINIMUM / MAXIMUM, RESP2 ...) are refused by name.

### X10. A LINK target's COMMAREA past the caller's record — DIFFERS (#4181)
- **What.** A LINK passes the COMMAREA by reference: the target sees the caller's storage from the area's first byte,
  for as long as its own DFHCOMMAREA (or the contract DTO it is typed with) reaches. When that is longer than the
  caller's record (GenApp's 71-byte ERROR-MSG LINKed to LGSTSQ, typed as the 99-byte CA-ERROR-MSG), z/OS shows the
  target whatever storage follows the record; so does GnuCOBOL, in its own layout.
- **The det port.** Gives the target the caller's bytes up to the end of the caller's record and LOW-VALUES past it
  (`Cobol.commarea`), and writes back as far (`Cobol.commareaBack`); it never reads past the record (before #4181 it
  failed there). A det caller passes the bytes themselves too (`CicsTask.link(..., area)`), so a det target sees every
  byte, the ones its contract DTO does not name included (CA-ERROR-MSG's leading FILLER).
- **Reached.** Not by a proof: no case runs a target that reads past its caller's record.
- **XCTL with a LENGTH past the target's DTO (#4501).** Same storage rule, from the sender's side: EIBCALEN
  at the target is the LENGTH, whatever the target's DFHCOMMAREA defines. The det port passes those LENGTH bytes
  (`DetCics.commareaOut`: the area's storage, LOW-VALUES past its record, in the region's EBCDIC), the target's
  DFHCOMMAREA takes the first ones and EIBCALEN is the LENGTH. Reached by ca-xctl-versions length-range, where LENGTH
  32767 fails LENGERR before any transfer and the COMMAREA compared is the 32,767 bytes of WS-BIG.
- **RETURN and LINK with a LENGTH past the DTO; bytes passed on (#4679).** IBM, EXEC CICS RETURN: COMMAREA / LENGTH
  is the data the next program of the conversation gets, and its EIBCALEN is LENGTH; EXEC CICS LINK: LENGTH is the
  COMMAREA's length (0-32763, else LENGERR RESP2 11), passed by reference. A RETURN TRANSID now passes its LENGTH bytes
  as XCTL does (CardDemo's COCRDLIC / COCRDSLC / COCRDUPC / COACTVWC / COACTUPC RETURN WS-COMMAREA, LENGTH 2000, over
  DTOs of a few hundred bytes); the equivalence harness reads them by the case's COMMAREA layout, as it reads the stub's
  RETURN area (`equivalence_cics.java_commarea`), so bytes past the layout are compared on neither side. A LINK with a
  LENGTH past the target's DTO lays that many bytes over the caller's storage (`Cobol.commarea`), not the DTO's size
  (GenApp's LINK of the 101-byte ERROR-MSG to LGSTSQ, LENGTH 101 over the 99-byte DTO). A receiver keeps the bytes past
  its own DFHCOMMAREA record (`Storage.beyond`): opaque -- it does not address them -- but a further RETURN / XCTL /
  LINK of that area with the LENGTH passes them on, and a LINK target's writes there go back by reference. Past
  what was passed, LOW-VALUES as above. RESP2 after a failed LINK is the stub's and CicsTask's: LENGERR 11, PGMIDERR 1
  (IBM, LINK conditions; `DetCics.linkResp2`); the others IBM lists (PGMIDERR 2 / 3, NOTAUTH 101, INVREQ ...) the
  region does not raise.

### X11. ASKTIME ABSTIME into a narrow field — DIFFERS
- **What.** ABSTIME is an 8-byte packed value (IBM: `PIC S9(15) COMP-3`). GenApp declares `WS-ABSTIME PIC S9(8) COMP`
  (4 bytes), so on z/OS ASKTIME writes past it into the next item, and FORMATTIME reads 8 bytes back from there.
- **Here.** Both sides store into the declared 4-byte field and agree (GenApp's error message dates come out as
  `01011900`); z/OS would not give that. Equal on both sides, so no verdict changes, but the date in GenApp's error
  messages is not z/OS's.
- **Reached.** Yes, by GenApp's SQL-fault tasks (M2).

### X12. DFHCOMMAREA referenced with EIBCALEN = 0 — UNDEFINED, masked
- **What.** IBM DBB EPSCMORT does `MOVE DFHCOMMAREA TO W-COMMUNICATION-AREA` before it tests EIBCALEN, so its first
  task (no COMMAREA) copies storage it was never given. On z/OS that is undefined: CICS establishes no addressability
  for an absent COMMAREA, and what the MOVE reads (or whether it abends) depends on the region.
- **Harness.** The CICS model gives LOW-VALUES there. A numeric field the task then returns still holding all
  LOW-VALUES was set by nothing (a MOVE leaves digits, never X'00'), and the Java side's COMMAREA DTO cannot hold an
  invalid number. In a scenario with `"commarea": null` only, such a field is left out of the comparison on both
  sides and counted (`undefined_commarea_fields` in the report): `equivalence_cics.mask_absent_commarea`. Every other
  field of that COMMAREA, and every field of every other scenario, is compared as usual.

### X13. An ESDS browsed by relative byte address — ASSUMED, REFUSED where IBM is silent (#4213)
- **What IBM documents** (CICS TS 6.x, EXEC CICS STARTBR / READNEXT / READPREV, and "Sequential reading (browsing)"):
  with RBA, RIDFLD "contains a relative byte address"; RBA on the STARTBR "applies to every READNEXT or READPREV command
  in the browse, and causes CICS to return the relative byte address of each retrieved record"; EQUAL "is the default
  for a direct ESDS browse" and GTEQ "is not valid for directly browsing an ESDS"; a RIDFLD of X'FF' characters, with
  RBA, positions at the end for READPREV; READPREV right after STARTBR needs the STARTBR's record to exist; to
  reposition, RIDFLD is set "in the same form as on the previous STARTBR" (an RBA). Both sides model that, with the
  keyed browse's rules for changing direction (`ggcics.c` rba_startbr / rba_read, `CicsTask.startbrRba` /
  `readnextRba` / `readprevRba`; the det translator emits them).
- **Assumed.** An ESDS of fixed-length records in arrival order whose RBA is the record's byte offset (record *n* at
  *n* × reclen), RIDFLD a big-endian fullword. On z/OS a record's RBA is its offset within the data set's control
  intervals, so where records do not fill a CI exactly (free space, the CIDF and RDFs at each CI's end) the RBAs after
  the first CI are larger than *n* × reclen. A program that only starts at RBA 0 or X'FFFFFFFF' and passes back the RBAs
  READNEXT returned (IBM DBB EPSMLIST) never sees the difference; one that computes an RBA would. A case may state an
  ESDS the estate never defines (`datasets.<name>.csd`: organization ESDS, reclen, why), as MortgageApplication needs
  for EPSMORTF; an IDCAMS `NONINDEXED` DEFINE with RECORDSIZE(n n) is read as one.
- **Refused by name** (exit 98 / `UnsupportedOperationException`, "... not modelled"): an RBA at which no record
  starts (IBM does not say whether VSAM answers NOTFND, INVREQ or ILLOGIC; past the end of the data included); RBA on a
  file that is not an ESDS (a KSDS by RBA); a keyed command on an ESDS; a browse that mixes RBA and keys; an RBA RIDFLD
  shorter than a fullword. By the translators: XRBA, RRN, READ / WRITE / DELETE by RBA, GTEQ or KEYLENGTH with RBA.
- **Reached.** Yes: mortgage-mlist (IBM DBB EPSMLIST) browses its ESDS from RBA 0 to ENDFILE.

### X14. READ ... INTO LENGTH — ASSUMED, REFUSED where IBM is silent (#4436)
- **What IBM documents** (CICS TS 6.x, EXEC CICS READ): LENGTH "specifies the length, as a halfword binary value, of
  the data area where the record is to be put. On completion of the READ command, the LENGTH parameter contains the
  actual length of the record"; a record longer than LENGTH is truncated to it, with LENGERR RESP2 11 ("the record is
  truncated, and the data area supplied in the LENGTH option is set to the actual length of the record"). Both sides
  model that for a keyed READ (`ggcics.c` GGCREAD with LENGTH in GG-LEN and set back on NORMAL / LENGERR;
  `DetCics.readInto` in the det port). Without LENGTH it is LENGTH OF INTO, as the CICS translator supplies it.
- **Assumed.** LENGERR RESP2 13 ("an incorrect length is specified for a file with fixed-length records") is not
  raised for a LENGTH other than the record's length: the cases' files are VSAM KSDSs, and GenApp itself reads its
  225- and 64-byte records with LENGTH set from EIBCALEN. The length set back is stored as a COBOL MOVE of a fullword
  into the program's item (CICS stores a halfword): the same below 10,000 bytes in a four-digit item, as every record
  here is.
- **Refused by name** (exit 98 / `UnsupportedOperationException`, "... not modelled"): a negative LENGTH; a record
  moved past the end of INTO (CICS writes the storage that follows INTO, which GnuCOBOL lays out unlike IBM's
  compiler, as X6); LENGERR on READ UPDATE (IBM does not say whether the record is then held for the REWRITE). The
  det translator still refuses LENGTH on READNEXT / READPREV and an RBA browse unless it is INTO's own length.
- **Reached.** NORMAL only: GenApp LGUPVS01 (LINKed by LGUPDB01 with LENGTH 225: a 64-byte record into a 1024-byte
  area, LENGTH set back to 64) and LGUCVS01. LENGERR is not reached by a proven scenario: every non-NORMAL READ in
  GenApp goes to LGSTSQ (X6), and both GenApp READs are UPDATE.

### X15. Terminal RECEIVE and SEND CONTROL — ASSUMED, REFUSED where IBM is silent (#4413)
- **What IBM documents** (CICS TS, EXEC CICS RECEIVE (3270 logical) and (LUTYPE2/LUTYPE3)): with INTO and no
  MAXLENGTH, LENGTH is "the maximum length that the program accepts" (below zero, zero); MAXLENGTH overrides it;
  longer data is truncated with LENGERR and LENGTH "set to the original length of data", or, under NOTRUNCATE, "CICS
  retains the remaining data and uses it to satisfy subsequent RECEIVE commands" with LENGTH the length returned.
  On an LUTYPE2 terminal EOC "occurs when a request/response unit (RU) is received with end-of-chain-indicator set",
  default action: ignore it (the 3270 logical unit's RECEIVE has no EOC). HANDLE CONDITION ERROR takes only a
  condition whose default action is an abend, so not EOC. SEND CONTROL sends device controls; none of its
  conditions can arise without a BMS logical message, partitions, LDCs or REQID. Both sides model it: `ggcics.c`
  GGCRECT / GGCRECS / GGCSCTL, and CicsTask.receive / sendControl with `DetCics.received` / `receivedSet`.
- **Assumed.** The terminal is the reference region's 3270 logical unit unless the case CSD defines it with a
  TYPETERM `DEVICE(LUTYPE2)` (cics-crucible SPEC section 2): then the input message is one chain, its single RU
  carries end-of-chain, and the RECEIVE returning its last byte raises EOC. RECEIVE INTO moves the data into INTO's
  first bytes and leaves the rest as it was. RECEIVE SET(ADDRESS OF record): the port's LINKAGE record keeps its own
  storage, so the data is copied into it and the bytes past the data are X'00' (on CICS they are storage IBM does not
  describe; a program reading past LENGTH reads undefined bytes).
- **Refused by name** (`Unsupported` / CicsError, "... not modelled"): SET of anything but ADDRESS OF a LINKAGE 01
  record; SET without MAXLENGTH (IBM's "the value indicated in the LENGTH option is assumed" would read the LENGTH
  that SET only sets) or without LENGTH(data-area); ASIS, BUFFER and the APPC / partition options; SEND CONTROL CURSOR
  without a value, PRINT, FORMFEED, ALTERNATE / DEFAULT, MSR, partitions, LDC, ACCUM / PAGING / SET / REQID. At run
  time: a RECEIVE with nothing retained (it would wait for the operator), and on an LUTYPE2 terminal a NOTRUNCATE
  RECEIVE that leaves data retained (IBM does not say whether it raises EOC).
- **Reached.** cics-crucible hc-terminal-receive (7 scenarios: LENGERR by RESP, by HANDLE CONDITION and by default,
  NOTRUNCATE pieces, SET, SEND CONTROL with CURSOR) and hc-terminal-eoc (3: EOC by RESP, HANDLE CONDITION, ignored by
  default), cobol-stub and the det port both passing the hand-written logs.

### X16. HANDLE AID, IGNORE CONDITION, PUSH / POP HANDLE, HANDLE CONDITION ERROR — MATCHED, REFUSED where IBM is silent (#4414, #4502)
- **What IBM documents** (CICS TS, EXEC CICS HANDLE AID, IGNORE CONDITION, HANDLE CONDITION, PUSH HANDLE, POP
  HANDLE; RESP and RESP2 options). HANDLE AID: a key's label, taken "after the input command is completed; that is,
  after any data received in addition to the AID has been passed to the application program"; ANYKEY is "any PA key,
  any PF key, or the CLEAR key, but not ENTER"; a key named without a label is deactivated; a task an AID started
  gets its input buffer on the first RECEIVE "(even if the length of the data is zero)"; RESP implies NOHANDLE, which
  "overrides both the HANDLE AID and the HANDLE CONDITION command". IGNORE CONDITION: control returns after the
  command with the EIB set; the last HANDLE or IGNORE for a condition wins. HANDLE CONDITION ERROR: "if the default
  action for such a condition terminates the task abnormally, and the condition ERROR has been specified, the action
  for ERROR is taken" (so not for EOC, ignored by default). PUSH HANDLE suspends the IGNORE CONDITION, HANDLE ABEND,
  HANDLE AID and HANDLE CONDITION state; POP HANDLE restores it, INVREQ when no PUSH HANDLE was executed at the
  current link level. Both sides model it: `ggcics.c` GGCHCND / GGCHAID / GGCAID / GGCPUSH / GGCPOP / GGCCOND (#4003,
  #4007), and the det port's `handlers` (-1: IGNORE), `aids` and `pushed` with `condition()` / `aid()` and
  DetCics.aidLabel / Handlers (#4414; the ERROR step of `condition()`, #4502).
- **Refused by name** (`CicsError` / `Unsupported` at translation, a DRIVER-ERROR or IllegalStateException at run
  time): IGNORE CONDITION ERROR (IBM does not say whether ERROR's action can be to ignore); a condition name IBM does
  not document; a HANDLE AID key that is no attention key, or RESP / NOHANDLE on it; at run time, a HANDLE AID label
  that applies to the key of an input command that also raised a condition (IBM does not say which CICS acts on
  first: MAPFAIL on a RECEIVE MAP after CLEAR or a PA key is the common case), and a key deactivated while ANYKEY
  has a label (IBM does not say whether ANYKEY then takes it). The stub took the condition first and gave the
  deactivated key to ANYKEY before #4414; both are refused on both sides now.
- **Reached.** cics-crucible hc-handle-aid (9: a key's own label, ANYKEY not ENTER, a deactivated key, RESP, PUSH /
  POP HANDLE, CLEAR and PA1 with no data), hc-ignore-error (9: IGNORE, ERROR, a condition's own HANDLE or IGNORE
  before ERROR, IGNORE overriding HANDLE, PUSH suspending IGNORE and ERROR, POP restoring, POP with nothing pushed)
  and hc-eoc-error (2: ERROR does not take EOC), cobol-stub and the det port both passing the hand-written logs.

### X17. Channels and containers — ASSUMED, REFUSED where IBM is silent (#4270 slice 1)
- **What IBM documents** (CICS TS, EXEC CICS PUT / GET / DELETE CONTAINER (CHANNEL), LINK, XCTL, ASSIGN, "The current
  channel", "The scope of a channel"). PUT: "If the channel does not exist, it is created"; with no CHANNEL "the
  current channel is implied"; APPEND appends, otherwise the data is overwritten; a new container's data type is BIT
  "unless FROMCCSID or FROMCODEPAGE option is specified"; FLENGTH below zero is LENGERR RESP2 1; no CHANNEL and no
  current channel is INVREQ RESP2 4 (1 with DATATYPE). GET: FLENGTH in, "the length of the data to be read", and out,
  "the length of the data in the container"; a shorter area is truncated with LENGERR RESP2 11; NODATA reads only the
  length; CHANNELERR RESP2 2, CONTAINERERR RESP2 10, INVREQ RESP2 4; "If INTOCCSID and INTOCODEPAGE are not
  specified, the value for conversion defaults to the CCSID of the region". DELETE: CHANNELERR 2, CONTAINERERR 10,
  INVREQ 4. LINK / XCTL CHANNEL: the channel (created empty if absent) is the target's current channel; a LINKed
  program "can also return containers to the calling program". ASSIGN CHANNEL: the current channel's name, blanks
  without one. CONTAINERERR (110) and CHANNELERR (122) abend AEZJ / AEZV by default. Both sides model it: `ggcics.c`
  GGCPUTC / GGCGETC / GGCDELC / GGCASCH and GGCLINK / GGCXCTL with GG-CHAN, and CicsTask putContainer / getContainer
  / deleteContainer / linkChannel / xctlChannel / assignChannel.
- **Assumed.** A container holds the program's bytes. A BIT container is never converted; a CHAR one put and got
  with no CCSID option is in the region's CCSID both ways, so it is not converted either -- the port keeps the bytes
  in its storage's page and the stub in its own, as each side keeps every other area. A channel is in the scope of
  the level that created it and of a level it is LINKed or XCTLed to; the LINKed program's channels die with its
  level. A GET's data goes into INTO's first bytes and leaves the rest as it was; FLENGTH is set back on NORMAL and
  LENGERR only (on another condition IBM does not say).
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run
  time): FROMCCSID, FROMCODEPAGE, INTOCCSID, INTOCODEPAGE, CONVERTST, CCSID (code-page conversion of a CHAR
  container); GET SET (a pointer to CICS's copy); BYTEOFFSET and PREPEND (no corpus program uses them); RETURN
  CHANNEL (the next task's channel: neither harness carries it, and no corpus program uses it); MOVE CONTAINER and
  STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER (later #4270 slices); LINK / XCTL with both CHANNEL and COMMAREA. At run
  time: a PUT naming the other data type for an existing container (IBM says DATATYPE "applies only to new
  containers" and also lists INVREQ RESP2 33 for "an attempt ... to change the data-type"); a channel an XCTL left
  behind (IBM's scope tables do not say); an FLENGTH past FROM / INTO, or a negative one on GET; a name that is
  blank or has an embedded blank (IBM's "illegal character" rules are not modelled).
- **Reached.** cics-crucible ca-channel-containers (2 scenarios: CHAR / BIT / APPEND, LINK and XCTL CHANNEL, the
  current channel, truncation and LENGERR, NODATA, CONTAINERERR / CHANNELERR / INVREQ by RESP and by HANDLE
  CONDITION, AEZJ by default), cobol-stub and the det port both passing the hand-written logs (crucible branch
  `cases/channel-containers`, not yet released or pinned).

### X18. Interval control: START / RETRIEVE / CANCEL / RUN TRANSID — ASSUMED, REFUSED where IBM is silent (#4270 slice 2)
- **What IBM documents** (CICS TS, EXEC CICS START, RETRIEVE, CANCEL, RUN TRANSID, "Expiration times"). START: INTERVAL
  "the expiration time as an interval of time that is to elapse from the time at which the START command is issued"
  ("The mm and ss are each in the range 0 - 59"); TIME / AT a time of day, "If you specify a time with an hours
  component that is greater than 23, you are specifying a time on a day following the current one", and "If you
  specify a task to start at any time within the previous six hours, it starts immediately"; AFTER / AT as "A
  combination of at least two of HOURS(0 - 99), MINUTES(0 - 59), and SECONDS(0 - 59)" or "one of HOURS(0 - 99),
  MINUTES(0 - 5999), or SECONDS(0 - 359999)"; INVREQ RESP2 4 / 5 / 6 for HOURS / hh, MINUTES / mm, SECONDS / ss out of
  range; LENGERR "if LENGTH is not greater than zero"; TRANSIDERR, TERMIDERR; IOERR when "A START operation uses a
  REQID name that exists. This condition occurs only when the FROM option is also used". RETRIEVE: the data and the
  RTRANSID / RTERMID / QUEUE values, LENGERR with "the data area is set to the original length of the data", ENDDATA
  (also for a START "that did not specify any of the data options FROM, RTRANSID, RTERMID, or QUEUE"), ENVDEFERR when
  "a RETRIEVE command specifies an option not specified by the corresponding START command"; "Tasks without
  terminals access only a single data record". RUN TRANSID: a child task that "runs asynchronously with the starting
  task", its token in CHILD's 16-character area, TRANSIDERR RESP2 1. Both sides model it: `ggcics.c` GGCSTRT /
  GGCRTRV / GGCCNCL / GGCRUNT and CicsTask startRequest / retrieve / cancel / runTransid; the det translator ports the
  commands onto CicsTask (`Cics.start`, `retrieve`, `cancel`, `run_transid`) and sets EIBTRMID from the task.
- **Assumed.** A TIME whose mm / ss is out of range is INVREQ with RESP2 5 / 6, as INTERVAL's (IBM names RESP2 for
  INTERVAL / AFTER / AT only); several values out of range on one START report the first of hours, minutes, seconds;
  the RTRANSID / RTERMID / QUEUE values come back on LENGERR too; a RUN child runs once its parent has ended (a parent
  that never FETCHes it cannot tell, SPEC 4); the child token's bytes are the harness's own, the same on both sides.
  A START's FROM bytes travel in the region's page, as a TS item's (#4528).
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run
  time): FETCH CHILD / ANY and FREE CHILD (a parent waiting for its child: a later #4270 slice); RUN / START CHANNEL
  (the child's copy of a channel); START USERID / SYSID / NOCHECK / ATTACH / BREXIT / FMH; RETRIEVE SET (a pointer)
  and WAIT; CANCEL of anything but a REQID. At run time: a START LENGTH past FROM's end (X6); a REQID that exists
  other than this task's own with FROM, reused with FROM; RETRIEVE INTO for a record whose START gave no FROM
  (whether that is ENVDEFERR); any RETRIEVE after ENVDEFERR (whether the record was used up); a RETRIEVE in a RUN
  child. The default abend codes of TRANSIDERR / TERMIDERR / IOERR / ENVDEFERR are not modelled: a program reaching
  one unhandled stops.
- **Reached.** cics-crucible gt-start-retrieve (6) and gt-terminal-coalesce (4) on the det port as on cobol-stub, and
  gt-start-options (7: data options, ENVDEFERR, RETRIEVE with no INTO, AFTER / AT and TIME(250000), INVREQ RESP2 6 / 5
  / 6 / 4, REQID IOERR, RUN TRANSID and its TRANSIDERR), cobol-stub and the det port both passing the hand-written
  logs (crucible branch `cases/start-retrieve-4270`, squid-protocol/cics-crucible#7, not yet released or pinned).

### X19. ASSIGN: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD — ASSUMED, REFUSED where the harness cannot decide (#4270 slice 3)
- **What IBM documents** (CICS TS 6.x, EXEC CICS ASSIGN, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-assign).
  STARTCODE "returns a 2-character value that indicates how the transaction that issued the request was started": `D`
  / `DS` a distributed program link, `QD` "Transient data trigger level", `S` "START command that did not pass data in
  the FROM option", `SD` "START command that passed data in the FROM option", `SZ` FEPI, `TD` "Terminal input or
  permanent transid", `U` "User-attached task". USERID: "If no user is explicitly signed on, CICS returns the default
  user ID" (DFLTUSER, default `CICSUSER`). FACILITY "returns a 4-byte identifier of the principal facility ... If this
  option is specified, and no facility is allocated, INVREQ occurs"; SCRNHT / SCRNWD "the height / width of the 3270
  screen defined for the current task. If the task is not initiated from a terminal, INVREQ occurs". INVREQ RESP2 5:
  "The task is not associated with a terminal; or the task has no principal facility"; "Default action: terminate the
  task abnormally" (AEIP).
- **The harness's facts.** Each is stated by whoever runs the task, never derived inside the runtime:
  CicsTask `withStartcode` / `withUserid` / `withScreen` and the stub's `$GGCICS_STARTCODE` / `$GGCICS_USERID` /
  `$GGCICS_FACILITY` / `$GGCICS_SCREEN`. The crucible runner states them from its scheduler and the reference region
  (cics-crucible SPEC 2): `TD` for a task a terminal step starts (typed input, or a pseudo-conversational RETURN
  TRANSID's next input), `SD` / `S` for a START-triggered task by whether its request(s) passed FROM, user `CICSUSER`
  (no security, nobody signs on), FACILITY the task's terminal, screen 24 x 80. Unstated (the equivalence harness's
  one-task scenarios), the option is refused at run time, not guessed.
- **Assumed.** An ASSIGN that raises INVREQ writes none of its data areas, the other options' included (IBM does not
  say; a crucible case never reads one after INVREQ). A START that passes RTRANSID / RTERMID / QUEUE but no FROM is
  `S` (IBM's codes are worded by FROM alone).
- **Refused by name** (`CicsError` / `Unsupported` at translation with the reason; exit 98 /
  UnsupportedOperationException / IllegalStateException at run time): OPID, OPCLASS, OPSECURITY, USERNAME (RACF
  facts; the region has no security); NETNAME (the harness's terminal has no network name); TERMCODE (a device type /
  model code); FCI (its code for a task with no terminal); DEFSCRNHT / DEFSCRNWD / ALTSCRNHT / ALTSCRNWD (only the one
  screen size is modelled); TWALENG, TCTUALENG, CWALENG (the work areas are not modelled); TASKPRIORITY; RETURNPROG;
  PRINSYSID; QNAME; and every other ASSIGN option (BMS, BTS, DPL and partner facts; no corpus program uses them). At
  run time: STARTCODE in a RUN TRANSID child (IBM lists no code for one), and in a terminal task started for several
  START requests (SPEC 4 coalescing) some with FROM and some without (which code it gets is undocumented).
- **Reached.** cics-crucible gt-assign-startcode (3: a terminal task, STARTs with and without FROM, a terminal START,
  a pseudo-conversational next task, an unhandled INVREQ abending AEIP), cobol-stub and the det port both passing the
  hand-written logs (crucible branch `cases/assign-4270`, not yet released or pinned).

### X20. SEND TEXT: TERMINAL, the default disposition — MATCHED, REFUSED where the region cannot decide (#4270 slice 4)
- **What IBM documents** (CICS TS 6.x, EXEC CICS SEND TEXT, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-text;
  Output disposition options: TERMINAL, SET, and PAGING,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=command-output-disposition-options-terminal-set-paging). TERMINAL
  "specifies that data is to be sent to the terminal that originated the transaction"; "The disposition option TERMINAL
  sends the output to the principal facility of your task"; "TERMINAL is the default value that you get if you do not
  specify another disposition"; "TERMINAL is the only disposition available in minimum and standard BMS".
- **Modelled.** TERMINAL is accepted with no code of its own (det.cics.OPTIONS says why; the stub's GGCSTXT call is
  unchanged): SEND TEXT TERMINAL sends what SEND TEXT sends, to the same place, and records the same SEND-TEXT event.
  cics-crucible SPEC 6.2 now says so (additive: the event's options are a sorted subset of ERASE FREEKB ALARM CURSOR
  WAIT LAST, and TERMINAL is never one). WAIT, FREEKB and ERASE are recorded as before.
- **Avoided.** SEND TEXT in a task with no principal facility (the SEND TEXT page lists no condition for it): the
  crucible case's started task tests for a terminal with ASSIGN FACILITY first, as SEQPNT / ASYNCPNT do.
- **Refused by name** (`CicsError` in the det port and `Unsupported` in the stub, both with the reason of the CICS command spec's SEND TEXT entry, `gitgalaxy/standards/cics`):
  ACCUM, PAGING, SET, REQID, HEADER, TRAILER, JUSTIFY, JUSFIRST, JUSLAST (a BMS logical message, completed by SEND
  PAGE, or the pages returned to the program, is not modelled); NLEOM, FORMFEED, HONEOM, L40, L64, L80 (printer
  formatting; the region's terminal is a 3270 display); LDC, OUTPARTN, ACTPARTN (partitions / logical device codes);
  MSR; FMHPARM; DEFAULT / ALTERNATE (only the one screen size is modelled). In the census only PL/I programs (dsf, a
  burned estate, outside the COBOL det translator) use ACCUM / PAGING / JUSTIFY / L80 / PRINT.
- **Reached.** cics-crucible gt-send-text-terminal (1 scenario: SEND TEXT with and without TERMINAL, a START TERMID
  task sending to the terminal the START named, a task with no terminal sending nothing), cobol-stub and the det port
  both passing the hand-written log (crucible branch `cases/send-text-4270`, not yet released or pinned).

### X21. EIBTASKN, a stated fact of the run — the value DIFFERS from z/OS, both sides MATCHED (#4270)
- **What IBM documents** (CICS TS 6.x, EIB fields including EIBRESP and EIBRESP2,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=reference-eib-fields): EIBTASKN "Contains the task number assigned to
  the task by CICS. This number appears in trace table entries generated while the task is in control. The format of
  the field is packed decimal. COBOL: PIC S9(7) COMP-3." Which number a task gets depends on the region's history
  (every task attached before it), so no program-level model can derive it.
- **The harness's fact.** EIBTASKN is stated by whoever runs the task, never derived inside a runtime, as the clock is
  (M4) and ASSIGN's facts are (X19). The CICS spec holds it (`gitgalaxy/standards/cics/eib.py`, `EIB_FACTS`); the stub
  gives `$GGCICS_TASKN` (`GGCTASKN`, which both drivers CALL after INITIALIZE DFHEIBLK, then MOVE to EIBTASKN), the
  Java side `CicsTask.withTaskNumber` (the det port's `runTask` stores `task.taskNumber()` into its EIB; the same at
  every LINK / XCTL level). The equivalence harness states, for each task, the scenario's `"taskn"`, else the case's,
  else 0, on both sides. 0 is the value every task had before it was stated (both sides' EIB is INITIALIZEd), and
  the one C12's RANDOM seed assumes.
- **So a proof says:** given the task number the case states, the port does what the COBOL does with it (CBSA's Db2
  programs write it into PROCTRAN's reference and their abend records; GenApp LGICDB01 moves it into a debug header).
  It does NOT say the value is z/OS's: no CICS region gives a task number 0, and a program whose behaviour depends on
  which number it gets (a key built from it colliding, a RANDOM seeded with it) is proven for the stated number only.
- **Refused by name.** A `"taskn"` that is not an integer from 0 to 9,999,999 (the field's PIC S9(7) COMP-3):
  `Unsupported` in the harness, exit 98 in the stub ("EIBTASKN: $GGCICS_TASKN is not a task number"),
  `IllegalArgumentException` in `withTaskNumber`.
- **Not stated yet.** The cics-crucible runner states no task number (its frames carry none; both sides read 0), so
  `proof_blockers.py` still counts `fact: EIBTASKN` for a crucible case's program. EIBRCODE, EIBCPOSN and the other
  EIB fields no command or driver sets stay zero / spaces on both sides and remain fact gaps.
- **Reached.** Every CICS task of every equivalence case (stated 0 unless the case says otherwise). Pinned by
  `tests/cics_crucible/test_cics_runtimes.py` (the stub and CicsTask, stated, unstated and refused) and
  `tests/cobol_mainframe/test_equivalence_cics.py` (the drivers, the scenario / case / default order).

### X22. READ GTEQ / GENERIC — ASSUMED, REFUSED where IBM is silent or the layout decides (#4270)
- **What IBM documents** (CICS TS 6.x, EXEC CICS READ, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-read):
  GENERIC "specifies that the search key is a generic key whose length is specified in the KEYLENGTH option"; GTEQ
  "specifies that, if the search for a record that has the same key (complete or generic) as that specified in the
  RIDFLD option is unsuccessful, the first record that has a greater key is retrieved"; EQUAL "specifies that the
  search is satisfied only by a record having the same key (complete or generic)". NOTFND RESP2 80: "An attempt to
  retrieve a record based on the search argument provided is unsuccessful." INVREQ RESP2 25: "The KEYLENGTH and
  GENERIC options are specified, and the length specified in the KEYLENGTH option is greater than or equal to the
  length of a full key"; 42: "... less than zero"; 26: KEYLENGTH without GENERIC "does not equal the length defined
  for the data set".
- **Modelled, on both sides.** The search key is RIDFLD's first KEYLENGTH bytes (GENERIC) or the whole key; the record
  read is the first, in key order, whose key starts with it or (GTEQ) is greater; none is NOTFND with RESP2 80 (the
  full-key READ still records 0 until spec PR 6 states IBM's RESP2 for every file command). READ UPDATE holds the
  record found (its own key). The stub: `GGCREAD` with GG-FLAGS `GTEQ` / `GENERIC` (`read_search`); the det port:
  `CicsTask.readSearch` over `DetCics.Store.search`.
- **ASSUMED.** RIDFLD is left as the program set it: IBM documents RIDFLD being set to the record's key for READNEXT /
  READPREV, not for READ (GenApp LGICVS01 MOVEs the found key itself). Key order is the browse's (D1: the stub's byte
  order, the det port's cp037 order); keys mixing letters and digits in one position would order differently.
- **Refused by name.** GTEQ with EQUAL and GENERIC without KEYLENGTH (the spec's option rules; both sides); a GENERIC
  KEYLENGTH not shorter than the key (INVREQ 25) or not above zero (42; zero is undocumented): the translator when it
  is a known constant, the stub at run time ("READ GENERIC KEYLENGTH ..."); a KEYLENGTH the translator cannot read as
  a constant, or a partial one without GENERIC (INVREQ 26, as before); a RIDFLD shorter than the bytes searched (CICS
  would read the storage after it, which GnuCOBOL lays out unlike IBM's compiler, X6).
- **Reached.** GenApp LGICVS01 (READ ... KEYLENGTH(10) GTEQ on KSDSCUST): equivalence case genapp-lgicvs01 -- the
  key on file, the next greater key, none past the end (NOTFND) and a RANDOM key in range, all PROVED. To run that
  terminal transaction the equivalence harness now states, as the cics-crucible runner does, a case's or scenario's
  `"startcode"` (ASSIGN STARTCODE, X19: `$GGCICS_STARTCODE` / `CicsTask.withStartcode`), `"terminal"` (an unformatted
  RECEIVE's input: `terminal.in` / `withTerminalInput`) and `"ts"` (the TS queues the task starts with: the stub's
  queue directory / `withTempStorage`, items in the region's page on the Java side, #4528), and compares READQ-TS and
  RECEIVE events on both sides. Its SEND TEXT FROM(WRITE-MSG-H) LENGTH(24) runs past FROM inside its record: the det
  port now sends those bytes (`DetCics.withinRecord`; past the record, refused as X6) where it cut the text at FROM's
  end. GenApp LGIPVS01's READ GENERIC GTEQ translates; no case runs it yet. No cics-crucible case: its runner models
  no file control yet (its files.cfg is empty), so the READ semantics are pinned by the runtime tests below. Pinned
  by `tests/cobol_mainframe/test_det_translate.py` (`test_read_gteq_*`) and `test_equivalence_cics.py`
  (`test_a_read_gteq_generic_search_is_named_to_the_stub`).

### X23. A COMMAREA of a stated length — ASSUMED, a reference past EIBCALEN REFUSED (#4270)
- **What IBM documents** (CICS TS 6.x, LINK: "COMMAREA(data-area) specifies a communication area that is to be made
  available to the invoked program ... LENGTH(data-value) specifies the length (halfword binary value) in bytes of the
  COMMAREA"; the invoked program's EIBCALEN is that length). A caller may pass fewer bytes than the invoked program's
  DFHCOMMAREA declares, and GenApp's services test for it: `IF EIBCALEN IS LESS THAN WS-REQUIRED-CA-LEN` -> '98', and
  WRITE-ERROR-MESSAGE's `IF EIBCALEN < 91`. What a program sees past EIBCALEN is the caller's storage after the area
  (a local LINK passes its address) or nothing CICS defines -- either way not the program's to read.
- **The harness's model.** A scenario states `"commarea_length": N` (1 to the record's length; never on a scenario
  with no COMMAREA): the caller passed the record's first N bytes and no more. Both sides give the program exactly N:
  the stub's driver hands the program the area GGCAREA chose -- the N bytes at the end of a page before an
  inaccessible one (`commarea.exact`) -- and the Java side states it (`CicsTask` with EIBCALEN N and
  `withExactCommarea()`): the det port's DFHCOMMAREA storage holds those N bytes for the task. The COMMAREA a LINKed
  program leaves is compared over the fields within the N bytes.
- **Refused, both sides; judged up to it.** A reference past EIBCALEN, read or write, stops the stub at that
  statement (the guard page faults: 98, "COMMAREA past EIBCALEN: not modelled") and the det port at the same one
  (`DetCics.PastFrom`, "COMMAREA past EIBCALEN (N bytes): not modelled"). As X6, the task is compared up to it and
  passes only when both sides refused there (the report's `x6` with `assumes: "X23"`); its end state is not compared.
  What z/OS shows there is not claimed.
- **Not covered.** A model port reads its COMMAREA DTO, which holds the whole record: it cannot refuse a reference past
  EIBCALEN, so a scenario that makes one fails against a model port (one side refused). Only the level-1 COMMAREA is
  exact: a LINK's or an XCTL's COMMAREA keeps the existing models (X10, and the stub's copy of an XCTL's LENGTH bytes),
  and a det port LINKing its own DFHCOMMAREA with a LENGTH past N passes what it has (`Cobol.commarea` clamps) where the
  stub stops. A guard page needs POSIX (mmap / mprotect): on Windows the stub refuses a stated length.
- **A failing SQL statement's host variables.** The det port binds a statement's input host variables before
  DetSql decides whether a planned SQL fault fires; the stub's injected fault reads none. A faulted statement whose
  host variables lie past EIBCALEN therefore stops the det port there (X23) and not the stub -- the task fails as
  "not the same refusal", never passes. GenApp LGACDB01 (EIBCALEN 90, its INSERT failing) and LGUCDB01 (under 91, its
  UPDATE failing) would reach `IF EIBCALEN < 91` that way; on z/OS the statement would read the caller's storage past
  the area, so those outcomes stay unreached.
- **Reached.** GenApp's Db2 services: LGACDB01 line 165 ('98', 60 bytes); LGDPDB01 line 143 ('98', 20 bytes) and
  WRITE-ERROR-MESSAGE's `EIBCALEN < 91` (40 bytes, the DELETE failing); LGIPDB01's five '98' returns (40 bytes) and
  `< 91` (the SELECT failing); LGACDB02 `< 91` (60 bytes, the INSERT failing). Each `< 91` task then LINKs LGSTSQ with
  CA-ERROR-MSG and is judged up to X6. Pinned by
  `tests/cobol_mainframe/test_equivalence_cics.py` (the guard page, the driver, the length's checks) and
  `tests/cobol_mainframe/test_det_translate.py` (the det port's cut storage).

### X24. A task started with a channel; the containers it leaves compared — ASSUMED (#4270)
- **What IBM documents** (CICS TS 6.x, "Scope of a channel"; RUN TRANSID CHANNEL: "the name of the channel that is
  to be passed to the child task"; FETCH CHILD CHANNEL: "the channel returned by the child task"; LINK CHANNEL: the
  called program's current channel, "what it puts there, the caller sees"). A service started by RUN TRANSID CHANNEL,
  or LINKed with CHANNEL, finds its input in containers on its current channel and leaves its result there for the
  parent to FETCH, or for the caller.
- **The harness's model.** A scenario states `"channel": {"name", "containers": {NAME: {"text" | "hex",
  "datatype"}}}`: the channel the caller passed (text in the case's data page; BIT unless CHAR, as PUT CONTAINER's
  default). Both sides build it before the program runs and make it the first program's current channel, the only
  one in its scope: the stub's `GGCCHIN` (channel.cfg), and the Java side's `CicsTask.withChannel` (with the new
  `Channel.with`). Unstated, the task has no current channel, as before (GET CONTAINER INVREQ RESP2 4).
- **What is compared.** At the task's end, the containers on that channel -- every one, by name, byte for byte, and
  the channel's name -- as a last CONTAINERS event (the stub's `containers.out`, written by GGCEND; the Java test reads
  `task.currentChannel()`), what the parent or caller sees. Dropped when the task abended (as a LINKed program's
  COMMAREA is) and for a task judged up to a refusal (X6, X23). The data type is not compared: no conversion is
  modelled (X17), so a parent sees the same bytes either way. Other channels the task made die with it and are not
  compared.
- **RUN TRANSID children.** The equivalence harness runs one task: a RUN TRANSID CHILD is compared as the command
  (TRANSID, RESP; `"transactions"` states the region's transaction definitions, else every one is defined), and the
  child is not run. Sound for a parent that never FETCHes it (CSSTATS2): nothing the child does can reach the parent.
  A FETCH CHILD / FETCH ANY is refused by the translator and the stub (X18).
- **A channel program's facade.** The generator gives a channel program `handleLink(XChannelIn)`, which no task
  facade carries yet (#4343): the java-facade side runs such a program through runTask, and its `entries` say so.
- **Reached.** The async credit-card services CRDTCHK, GETADDR, GETNAME, CSSTATUS (which LINKs GETPOL and GETSPND)
  and CSSTATS2 (RUN TRANSID GETP / SPND): their '0001' and other-account branches, and the containers they PUT.
  Pinned by `tests/cobol_mainframe/test_equivalence_cics.py` (the stub's channel in and containers out, the
  comparison, the drop on abend).

### X25. SYNCHRONIZED slack bytes -- 8-byte binary alignment ASSUMED to be IBM's fullword (#4266)
- **The rule the layout model follows.** IBM Enterprise COBOL aligns a SYNCHRONIZED binary item of up to 4 digits on a
  halfword and one of 5 to 18 digits (the 8-byte S9(10)-S9(18) included) on a fullword, COMP-1 / INDEX / pointers on a
  fullword and COMP-2 on a doubleword, counted from the start of the record, which is doubleword-aligned
  (<https://www.ibm.com/docs/en/cobol-zos/6.4?topic=entry-synchronized-clause>). The slack bytes count toward the
  group that holds the item.
- **Between the occurrences of a table** (an OCCURS group that holds SYNC items): the group's size, with the slack inside it,
  is divided by the largest boundary any elementary item in it needs; when the remainder r is not zero, the compiler adds
  m - r slack bytes at the end of each occurrence
  (<https://www.ibm.com/docs/en/cobol-zos/6.4?topic=clause-slack-bytes-within-records>). `record_layout` and
  `_storage_spans` do this. The rule is read from IBM's text; it was not run on z/OS.
- **The assumption.** The 8-byte binary stays on IBM's fullword because z/OS is the target. GnuCOBOL and Micro Focus may
  align an 8-byte binary on a doubleword. If the GnuCOBOL oracle ever compares slack bytes (offsets after such an item,
  or a record's length), the two can differ.
- **Reach today.** No committed case reaches it: no committed oracle case or answer-key layout holds an 8-byte binary
  with SYNC after an off-boundary item. Status: ASSUMED.

### X26. BIF DEEDIT, INQUIRE / SET TERMINAL UCTRANST, DFHVALUE — ASSUMED, REFUSED where IBM is silent (#4415 slice 1)
- **BIF DEEDIT** (CICS TS 6.x, EXEC CICS BIF DEEDIT, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-bif-deedit).
  "alphabetic and special characters are removed from an EBCDIC data field", "the remaining digits right-aligned and
  padded to the left with zeros as necessary"; "If the field ends with a minus sign or a carriage-return (CR), a negative
  zone (X'D') is placed in the rightmost (low-order) byte"; "If the zone portion of the rightmost byte contains one of
  the characters X'A' through X'F', the rightmost byte is returned unaltered (see the example). This permits the
  application program to operate on a zoned numeric field"; "A 1-byte field is returned unaltered, no matter what the
  field contains". The page's examples: `14-6704/B` in 9 bytes returns `00146704B`, `$25.68` returns `000002568`.
  LENGERR "if the LENGTH value is less than 1" (default action: terminate the task abnormally, AEIV); the page lists no
  RESP2, so none is claimed (RESP2 0 is written). Implemented as `DetCics.deedit` (the port) and `GGCDEED` (the stub):
  the first LENGTH bytes of FIELD taken in the region's page (the port: the program's page `CS` to `REGION`; the stub:
  7-bit ASCII to CCSID 037 by the table python's cp037 gives), edited on those bytes, and taken back.
- **Assumed.** LENGTH defaults to the field's length (the COBOL translator supplies it; CBSA's five programs give none:
  IBM's page does not say for COBOL); a trailing minus sign or CR takes precedence over the zoned-byte rule for the
  rightmost byte (`CR` ends in X'D9', a zoned byte, so the two statements overlap); the digits are X'F0'-X'F9' only;
  "ends with" is literal (a sign followed by blanks is no sign); a `CR` is upper case. The crucible case
  hc-deedit-uctranst uses none of these.
- **Refused by name** (exit 98 / UnsupportedOperationException): a field in which no digit remains and no rightmost byte
  is zoned (IBM does not say what it becomes), a character beyond 7-bit ASCII, a LENGTH past the field (as X6).
- **INQUIRE TERMINAL UCTRANST / SET TERMINAL UCTRANST** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-terminal,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-set-terminal; CVDAs: API Reference, "CVDAs and numeric values":
  UCTRAN 450, NOUCTRAN 451, TRANIDONLY 452). INQUIRE: the value "comes from the UCTRAN option of the associated TYPETERM
  definition"; TERMIDERR RESP2 1 "The named terminal cannot be found". SET: INVREQ RESP2 43 "Invalid UCTRANST CVDA",
  TERMIDERR RESP2 23. The terminal's UCTRANST is a fact the run states (`CicsTask.withUctranst`, the stub's
  `$GGCICS_UCTRANST`; the crucible runner takes it from the case terminal's TYPETERM `UCTRAN(YES|NO|TRANID)` as UCTRAN /
  NOUCTRAN / TRANIDONLY, name for name: ASSUMED, the pages do not tabulate it); unstated, INQUIRE is refused. IBM does
  not say when a SET takes effect or whether it outlives the task, so a terminal RECEIVE after a SET in the same task
  is refused, and a SET is the task's view only (the harness does not carry it to a later task). The UCTRANST of a
  terminal other than the task's is refused (its TYPETERM is not stated). Every other option of the two commands is
  refused with a reason.
- **DFHVALUE(name)** in a program the stub runs is replaced by IBM's CVDA number (det/cvda.py, generated from the API
  Reference's table); a name that is no CVDA is refused by name. The det port already took it in expressions.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven through cics-crucible hc-deedit-uctranst (3) on
  the cobol-stub side and the det port.

### X27. RETURN ... IMMEDIATE, LINK ... SYNCONRETURN — ASSUMED, REFUSED where IBM is silent (#4270 slice)
- **RETURN IMMEDIATE** (CICS TS 6.x, EXEC CICS RETURN, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-return).
  IMMEDIATE "ensures that the transaction specified in the TRANSID option is attached as the next transaction regardless
  of any other transactions enqueued by ATI for this terminal. The next transaction starts immediately and appears to the
  operator as having been started by terminal data." COMMAREA: "The communication area specified is passed to the next
  program that runs at the terminal." So the runtime ends the task, the next task is TRANSID's, at the same virtual time,
  with the COMMAREA, and the terminal's next operator step is not used up by it (`CicsTask.returnImmediate`, `GGCRETI`,
  the runner's `immediate` trigger). Conditions: INVREQ RESP2 1 "A RETURN command with the TRANSID option is issued in a
  program that is not associated with a terminal"; INVREQ RESP2 2 "A RETURN command with the CHANNEL, COMMAREA, or
  IMMEDIATE option is issued by a program that is not at the highest logical level"; LENGERR RESP2 11 "The COMMAREA
  length is less than 0 or greater than 32763". The command then returns to the program (RESP/RESP2, else the condition's
  default action). The task's terminal is a stated fact (`CicsTask.withTermid`, `$GGCICS_FACILITY`); unstated in the stub,
  refused. The INVREQ and LENGERR checks are made for IMMEDIATE only: the plain RETURN TRANSID still never returns to the
  program here (no corpus program tests its RESP).
- **Assumed.** The immediate task's STARTCODE is `TD` ("started by terminal data"; the runner states it, ASSIGN STARTCODE
  would read it). Nothing else about it is claimed: IBM does not say what EIBAID holds, or what an unformatted terminal
  RECEIVE returns ("terminal data" that was never typed), so the crucible runner gives the task no EIBAID and no input,
  the log's `eibaid` is null, and the case reads neither.
- **Refused by name.** RETURN IMMEDIATE without TRANSID (IBM does not say what it attaches); a task with no terminal
  below level 1 (IBM lists INVREQ RESP2 1 and 2 and no precedence); an unstated terminal in the stub.
  RETURN CHANNEL stays refused (register: no corpus program uses it). IBM does not say how an immediate task orders
  against an expired START request of another transaction; the runner runs it first, and a case never makes the order
  observable.
- **LINK SYNCONRETURN** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-link): "Specifies that the server region
  named on the SYSID option is to take a sync point on successful completion of the server program", and "SYNCONRETURN is
  only applicable to remote links, it is ignored if the link is local." Every program of the modelled region is local (SYSID
  is refused by name), so the option is accepted and changes nothing: the linked program is not given a unit of work of its
  own, a SYNCPOINT or ROLLBACK in it is the caller's. The remote-only conditions (INVREQ RESP2 14, ROLLEDBACK RESP2 29,
  SYSIDERR, TERMERR) cannot occur.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven through cics-crucible pc-return-immediate (4) on
  the cobol-stub side and the det port.

### X28. FORMATTIME RESP, ASKTIME NOHANDLE, READQ TS LENGTH(LENGTH OF), RECEIVE MAP ASIS — ASSUMED, REFUSED where IBM is silent (#4737)
- **FORMATTIME** (CICS TS 6.x, EXEC CICS FORMATTIME, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-formattime).
  INVREQ (RESP 16): RESP2 1 "The ABSTIME value is less than zero or not in packed-decimal format", RESP2 2 "Invalid CVDA
  value for the STRINGFORMAT option"; the default action is to terminate the task abnormally (AEIP). The runtimes check the
  ABSTIME value (`CicsTask.formattimeCheck`; the stub's COBOL) when RESP or RESP2 is given and write RESP 16 / RESP2 1 for one
  below zero (nothing formatted; EIBRESP / EIBRESP2 and RESP / RESP2 written). With neither, INVREQ's handling (a HANDLE
  CONDITION label, the default abend AEIP) is REFUSED at run time by name for an ABSTIME below zero (`CicsTask.formatDate` /
  `formatTime`; the stub's `FORMATTIME ABSTIME < 0 NO RESP: not modelled`): the corpora's FORMATTIMEs take the
  ABSTIME of an ASKTIME. "Not in packed-
  decimal format" is the declared storage's business: a port reads ABSTIME by its declared usage, so it is not checked
  (X4's `ASKTIME` size note applies). STRINGFORMAT is not an option here (refused by name). IBM does not say what the
  output areas hold after INVREQ: the runtimes leave them alone and the case does not read them (ASSUMED).
- **ASKTIME NOHANDLE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-asktime): "ASKTIME updates the date (EIBDATE)
  and CICS time-of-day clock (EIBTIME) fields in the EIB"; NOHANDLE is one of the common options and the page lists no
  condition, so it suppresses nothing. ABSTIME is optional: without it only the EIB fields change, and the region keeps those
  as dispatched (X4). `NOHANDLE` directly after the verb is an option, not a second verb word (the translator's parser).
- **READQ TS LENGTH(LENGTH OF area)** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readq-ts): "If you specify INTO,
  LENGTH defines the maximum length of data that the program accepts"; a longer item "is truncated to that value and the
  LENGERR condition occurs"; the LENGTH data area is "set to the original length of the data record". `LENGTH OF` is a
  compile-time constant, so it is the maximum and CICS's length goes to a temporary nobody reads: both sides do not store it
  back (a literal LENGTH is the same). IBM lists no RESP2 for LENGERR.
- **RECEIVE MAP ... ASIS** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-receive-map): ASIS "specifies that
  lowercase characters in the 3270 input data stream are not translated to uppercase" (no effect on the first RECEIVE of a
  transaction). The runtimes deliver the operator's input as typed, which is what ASIS asks for. A RECEIVE MAP without ASIS on
  a UCTRAN(YES) terminal (X26) would translate on z/OS: the runtimes do not model that translation and no case reads it
  (REFUSED where IBM is silent: the page does not tabulate UCTRAN against ASIS).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven through cics-crucible hc-resp-options (4) on the
  cobol-stub side and the det port.

### X29. INQUIRE ASSOCIATION, DELETEQ TS, QUERY COUNTER, RECEIVE MAP TERMINAL — ASSUMED, REFUSED where IBM is silent (#4415 slice 2)
- **INQUIRE ASSOCIATION** (CICS TS 6.x, CICS SPI command INQUIRE ASSOCIATION,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-association). ASSOCIATION "Specifies the 4-byte number of the
  task for which you want to retrieve association data"; ODAPPLID "the 8-character APPLID taken from the origin descriptor
  associated with this task"; ODUSERID "the 8-character user ID under which the originating task ran"; ODFACILNAME "the
  8-character name of the facility" (a transient data queue, terminal or system); ODNETWORKID "the 8-character network
  qualifier for the origin region APPLID"; ODFACILTYPE a CVDA for the facility type that started the originating task (APPC,
  ASRUNTRAN, BRIDGE, EVENT, IIOP, IPECI, IPIC, JVMSERVER, LU61, MRO, NODEJSAPP, NONE, RRSUR, RZINSTOR, SCHEDULER, SOCKET,
  START, STARTTERM, TERMINAL, TRANDATA, WEB, XMRUNTRAN; numbers: det/cvda.py). Conditions: INVREQ RESP2 2 "The command was
  specified with no arguments", NOTAUTH RESP2 100, TASKIDERR RESP2 1 "The task specified on the ASSOCIATION option was not
  found". The origin data page (Association data, "Origin data characteristics": "details of its point of origin is placed
  into task context information called origin data", "created when a new request first arrives at a CICS region") does not
  say what the five fields hold for a task a terminal started, so they are **a fact the run states** (`CicsTask.withOrigin`,
  the stub's `$GGCICS_ORIGIN` = `applid,userid,facilname,networkid,faciltype`; the cics-crucible runner takes them from the
  case's optional `origin` object, for a task that terminal input started -- a START, RUN or RETURN IMMEDIATE task is not
  stated): never a default; unstated, INQUIRE ASSOCIATION is refused at run time on both sides. Only the task's own number
  is modelled: the operand must be `EIBTASKN` itself (IBM gives no representation for the 4 bytes; a literal or a copy is
  refused by the translator and the stub's harness), so TASKIDERR does not arise (the task exists) and NOTAUTH does not
  (the reference region has no security). A command with no origin option is REFUSED (the INVREQ RESP2 2 sentence does not
  say whether ASSOCIATION alone is "no arguments"; a case does not use it either). Every other option
  (ODTASKID, ODTRANSID, the previous-hop and other association-data options) is refused by name.
- **DELETEQ TS** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-deleteq-ts). QUEUE / QNAME; "Every condition
  below has the default action of terminating the task abnormally": INVREQ (16) "The queue was created by CICS internal code, or
  the queue name is all binary zeroes", ISCINVREQ (54), LOCKED (100) "restricted because a unit of work failed indoubt",
  NOTAUTH (70), QIDERR (44) "the queue can't be found in main or auxiliary storage", SYSIDERR (53). The page lists **no
  RESP2**, so 0 is written. Modelled: the whole queue and its READQ NEXT position are removed (`CicsTask.deleteqTs`, the
  stub's `GGCDELQ`); QIDERR for a queue that is not there; INVREQ for a name whose bytes up to its trailing blanks are all
  binary zeros. ISCINVREQ / SYSIDERR need SYSID (refused), LOCKED needs a recoverable queue (the region's are not, SPEC 2),
  NOTAUTH needs security (none). A DELETEQ TS leaves no event of its own in the log: its effect is what a later READQ TS /
  WRITEQ TS answers.
- **QUERY COUNTER** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-query-counter-query-dcounter). "VALUE ... Returns the
  current value. CICS returns a fullword signed binary value for the COUNTER command"; INVREQ RESP2 201 "Named counter not
  found"; LENGERR RESP2 1-3 for a value too large for a fullword. Modelled: COUNTER, POOL (omitted: the 8 blanks), VALUE, the
  value left as it is (unlike GET COUNTER) from the region's named counters (`CicsTask.withCounters`, the stub's
  `counters.cfg`); a counter beyond a fullword is refused by name (IBM returns the low-order 32 bits with LENGERR; not
  modelled); MINIMUM / MAXIMUM (the counters' limits are not stated by the run) and NOSUSPEND (BUSY needs a coupling-facility
  structure) are refused as options. **Not proven through the crucible**: the reference region has no named counters, so
  this is proven by unit tests of both runtimes on IBM's text (tests/cics_crucible/test_cics_runtimes.py). Note: the existing
  GET COUNTER answered NOTFND for a counter that is not there, where IBM's GET COUNTER page lists INVREQ RESP2 201 -- fixed in
  X30.
- **RECEIVE MAP ... TERMINAL** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-receive-map). TERMINAL "specifies that
  input data is to be read from the terminal that originated the transaction". The task's terminal is the only one the
  region has, and the one every RECEIVE MAP already reads, so the option changes nothing. (The page does not say whether it is
  the default; for a terminal task the two are the same.)
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven through cics-crucible hc-inquire-deleteq on the
  cobol-stub side and the det port (INQUIRE ASSOCIATION, DELETEQ TS, RECEIVE MAP TERMINAL).

### X30. DEFINE COUNTER, DELETE COUNTER; GET COUNTER's missing counter is INVREQ RESP2 201 — ASSUMED, REFUSED where IBM is silent (#4270)
- **DEFINE COUNTER** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-define-counter-define-dcounter). COUNTER "the 16-byte
  name of a fullword (signed) counter ... uppercase letters, digits, underscores, and $, #, @ ... cannot start with a number or
  underscore"; POOL "an 8-character pool selector ... If you omit the name of the pool, a pool selector value of 8 blanks is
  assumed" (valid characters A-Z, 0-9, $, @, #, _); VALUE the initial value ("If you omit both the VALUE and MINIMUM parameters,
  the named counter is created with an initial value of zero"). Conditions: INVREQ RESP2 202 "Duplicate counter name. A named
  counter of this name already exists" (the page lists **no DUPREC**), 403 "POOL contains invalid characters or embedded spaces",
  404 "COUNTER contains invalid characters or embedded spaces", 406 / 407 (VALUE / MINIMUM / MAXIMUM outside the limits),
  301-311 (counter server and options table: the region has no server), BUSY RESP2 500 (NOSUSPEND during a coupling-facility
  rebuild). Modelled: COUNTER, POOL, VALUE (omitted: zero), the region's counters keyed by pool and name (`CicsTask.defineCounter`,
  the stub's `GGCDCNT` on `counters.cfg`); 202, 403, 404. **Refused by name**: MINIMUM / MAXIMUM (the default limits are
  "low-values" / "high values" and IBM does not say how they read as signed values), NOSUSPEND, DCOUNTER (unsigned doublewords);
  at run time a VALUE below zero (406 depends on the unstated minimum) and a counter name of blanks only (IBM states the
  character rules, not an empty name).
- **DELETE COUNTER** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-delete-counter-delete-dcounter). Conditions: INVREQ
  RESP2 201 "Named counter not found" (the page lists **no NOTFND**), 403, 301-311, BUSY 500. The page lists no 404: a name
  outside the rules is simply a counter that is not there (201). Modelled (`CicsTask.deleteCounter`, `GGCXCNT`); NOSUSPEND,
  DCOUNTER refused.
- **GET COUNTER fixed** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-get-counter-get-dcounter). The page lists INVREQ
  RESP2 201 "Named counter not found" and no NOTFND; the runtimes answered NOTFND (RESP 13, RESP2 0) since X9. Both now answer
  INVREQ (16) RESP2 201 (`CicsTask.getCounter` returns {RESP, RESP2, value}; the det translator writes both; the stub's
  `GGCGCNT`), and INVREQ 403 / 404 for a pool / counter name outside IBM's characters, as DEFINE does; QUERY COUNTER likewise.
  **No proven case moved**: no cics-crucible case, equivalence case or committed port used GET COUNTER (only a translator unit
  sample), so no verdict changed; hc-named-counters is the first that does, and it proves INVREQ RESP2 201. GET COUNTER's
  other options (INCREMENT, WRAP, REDUCE, COMPAREMIN / COMPAREMAX, NOSUSPEND) stay refused by name (X9).
- **Not modelled / unobserved**: RESP2 of a command that completed is 0 (IBM states none: the case logs RESP2 only for a failed
  command); the order of 403 and 404 when both a pool and a counter name are invalid (the case never provokes both; the runtimes
  check the pool first); the value area of a failed GET / QUERY (not written).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven through cics-crucible `hc-named-counters` (2 scenarios,
  hand-traced) on the cobol-stub side and the det port; unit-proven on `CicsTask` and the stub C
  (tests/cics_crucible/test_cics_runtimes.py).

### X31. SEND MAP / RECEIVE MAP for a map its mapset does not hold -- abend ABM0, no condition -- ASSUMED (#4270)
- **What IBM says.** SEND MAP, MAPSET: "If this option is not specified, the name given in the MAP option is assumed to be
  that of the mapset" (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-map); the mapset "must reside in the CICS
  program library" and "can be defined either by using RDO or by program autoinstall". SEND MAP's conditions are INVMPSZ (38,
  no RESP2: "the specified map is too wide for the terminal") and INVREQ (16; RESP2 200 "Command not allowed for a distributed
  program link server program"; also a map without field specifications), RECEIVE MAP's (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-receive-map)
  EOC, EODS, INVMPSZ, INVPARTN, INVREQ (a nonterminal task), MAPFAIL (36, "the data to be mapped has a length of zero or does not
  contain a set-buffer-address (SBA) sequence"), PARTNFAIL, RDATT, UNEXPIN. **Neither page lists a condition for a map that
  is not found.** The abend code reference has one: ABM0, "The map specified for a basic mapping support (BMS) request could
  not be located"; system action "The transaction is abnormally terminated with a CICS transaction dump"; user response "Check
  if the map has been defined. If it has, check that it has been specified correctly"
  (https://www.ibm.com/docs/SSGMCP_6.1.0/reference-abend-codes/abend-codes/ABxx_abend_codes/ABM0.html; modules DFHMCP, DFHMCX,
  DFHMCY). A mapset that is not defined at all: PGMIDERR, when autoinstall for programs is off (SET SYSTEM,
  https://www.ibm.com/docs/en/cics-ts/5.5.0?topic=commands-set-system, "a program, map set, or partition set that is not
  defined") -- not modelled.
- **Modelled.** A map the (constant) MAP names that is not one of the maps its (constant, or defaulted) mapset holds, in an
  estate whose BMS source defines that mapset: abend ABM0, as EXEC CICS ABEND ABCODE('ABM0') ends the task -- the first
  active HANDLE ABEND exit from the issuing level upward gets control, else the task is terminated and its unit of work
  backed out; the ABEND event's `cause` is `system` (cics-crucible SPEC, additive); nothing is sent or received, EIBRESP is
  not written. Translator: `Cics.map_not_found` (`CicsTask.abendMapNotFound`); stub: `GGCSMAP` / `GGCRECV`, the mapsets and
  their maps stated by the run in `$GGCICS_MAPSETS` (`MAPSET=MAP,MAP;...`, the cics-crucible runner takes them from the
  case's `maps`), a mapset not stated is not checked. BNK1CCS (CBSA) names its mapset BNK1CCM as a map, with no MAPSET, and
  now translates whole.
- **ASSUMED.** (1) ABM0 is the abend for a map missing from a mapset that exists: IBM's text says "the map ... could not be
  located" and does not say "in the mapset". (2) RESP / RESP2 do not turn the abend into a condition: IBM lists no condition
  for it, so the abend is taken to be unconditional; no crucible scenario gives the command RESP. A map not found is never
  PGMIDERR here. Refused (unchanged): a MAP / MAPSET that is not a constant, a map of no BMS source we hold in an unknown
  mapset ("no generated screen for map"), and the mapset-undefined case.
- **Proof.** cics-crucible `hc-map-not-in-mapset` (hand-traced; `in-mapset`, `omitted-mapset`, `receive`, `exit`): the
  cobol-stub and the det port (java-ported) agree with the log; unit tests on both runtimes
  (`test_det_cics_map_names_4270.py`, `test_equivalence_cics.py`).

### X32. INQUIRE URIMAP's browse, WRITE OPERATOR — ASSUMED, REFUSED where IBM is silent (#4270, zECS ZECSPLT)
- **INQUIRE URIMAP** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-urimap; "Browsing resource definitions",
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-browsing-resource-definitions). "You can also browse through all the URIMAP
  definitions installed in the region, using the browse options (START, NEXT, and END)"; START "does not produce any
  information". Conditions: END RESP2 2 "There are no more resource definitions of this type" (RESP2 8, the definition deleted since the browse began, cannot
  arise: nothing installs or discards a definition in a task); ILLOGIC RESP2 1 "You have issued a START command when a browse of
  this resource type is already in progress" (the page words a NEXT or END with no browse as ILLOGIC too and gives it no RESP2 of
  its own); NOTFND RESP2 3 "The URIMAP cannot be found" (the direct form); NOTAUTH RESP2 100 (no security in the region).
  URIMAP "Returns the 8-character name", PATH "a 255-character data area containing the path component of the URL", TRANSACTION
  "the 4-character name of an alias transaction". Modelled (`CicsTask.inquireUrimapStart` / `Next` / `End`, the stub's `GGCURIB`
  and `GGCURIP`): the browse over the definitions the run states, END RESP2 2, ILLOGIC RESP2 1.
- **What IBM leaves open, and what we do.** (1) The browse order: stated, with the definitions, by whoever runs the task (the
  crucible runner states the CSD's order; an equivalence case its "urimaps", #4270; a case must not depend on it). (2) The padding of a value shorter than its length:
  blanks (ASSUMED, as every character value CICS returns), at most the program's area (an area longer than IBM's length keeps
  its tail, which is how a PIC X(256) takes the 255-character PATH). (3) The data areas on END, ILLOGIC or any other condition:
  left alone (ASSUMED; they are written on NORMAL only). **Refused by name**: the direct form INQUIRE URIMAP(name) (the translator),
  every attribute but URIMAP / PATH / TRANSACTION (HOST, SCHEME, USAGE ...), an output area with START or END, a NEXT or END with
  no browse started (the ILLOGIC RESP2 is not stated: both runtimes stop the run), and definitions the run does not state.
- **WRITE OPERATOR** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-write-operator). TEXT "a data value containing the text
  to be sent" (COBOL: "a data-area"); TEXTLENGTH "required only for C and C++" (the area's length is the text's); "If the data value begins with DFHnnnn or DFHaannnn, the message is treated as a
  CICS message and is reformatted accordingly"; over 113 characters CICS formats a multi-line WTO. Modelled: the plain message,
  recorded as a WRITE-OPERATOR event with its text (`CicsTask.writeOperator`, the stub's `GGCWTO`); RESP NORMAL (ERROR RESP2 1,
  the MVS WTO failing, cannot arise here). **Refused by name**: every option but TEXT (ROUTECODES, NUMROUTES, CONSNAME, ACTION and
  its CVDAs, REPLY, TIMEOUT ...), a literal TEXT, and at run time a text IBM reformats or splits (DFHnnnn / DFHaannnn prefix, over 113
  characters).
- **Not modelled / unobserved**: the console itself (the event is the message sent, not a screen); whether the case's browse order
  matches z/OS (it cannot be told from IBM's pages, so the case counts and never orders).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven through cics-crucible `gt-urimap-browse` on the cobol-stub
  side and the det port; unit-proven on `CicsTask` and the stub C (tests/cics_crucible/test_cics_runtimes.py). zECS's ZECSPLT
  translates whole and compiles.

### X33. DOCUMENT CREATE and DOCUMENT RETRIEVE (the document handler) — ASSUMED, REFUSED where IBM is silent (#4769, zECS)
- **DOCUMENT CREATE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-document-create). DOCTOKEN "a 16-byte area that
  receives the CICS-generated token"; TEXT "copied unchanged"; BINARY "used unchanged as the document content"; TEMPLATE "the
  48-byte name of an RDO-defined template, padded with blanks"; LENGTH "the length of the TEXT, BINARY or FROM buffer".
  Conditions: LENGERR RESP2 1 "LENGTH is negative"; NOTFND RESP2 3 "The TEMPLATE was not found or was misnamed" (the page words
  TEMPLATERR as "the template does not exist" too: the table's NOTFND 3 is taken); NOTAUTH (no security in the region).
  Modelled (`CicsTask.documentCreateEmpty` / `documentCreateData` / `documentCreateTemplate`, the stub's `GGCDOCC`): a
  document is the bytes the task built, in the program's own code page, kept as long as the task (every program it LINKs to
  shares it); the token goes to the area on NORMAL only.
- **DOCUMENT RETRIEVE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-document-retrieve). MAXLENGTH "the maximum
  amount of data the buffer can receive"; LENGTH "the amount of data returned. If the document is truncated, this is the exact
  length required to return the whole document"; there is no TRUNCATE option, "truncation is reported through LENGERR with
  RESP2 2". Conditions: LENGERR RESP2 1 "MAXLENGTH is less than zero. LENGTH is not returned", RESP2 2 "The receiving buffer is
  zero length or too short", NOTFND RESP2 1 "The document was not created, or the name is incorrectly specified".
  Modelled (`CicsTask.documentRetrieve`, `DetCics.putDocument`, the stub's `GGCDOCR`).
- **What IBM leaves open, and what we do.** (1) The DOCTOKEN's value is ours (`GGDOC` and eleven digits, blank-padded to the
  area); a program must not read meaning into it. (2) The installed DOCTEMPLATEs are a fact whoever runs the task states
  (`CicsTask.withDoctemplates`, `$GGCICS_DOCTEMPLATES`, an equivalence case's "doctemplates", name to text), after the
  definition's own attributes (zECS's `APPENDCRLF(YES) TYPE(EBCDIC)`: the record's CRLF) are applied by whoever states it;
  unstated, a TEMPLATE is refused. (3) The rest of INTO after a short document, and LENGTH on any condition but NORMAL and
  LENGERR RESP2 2: left alone (ASSUMED). (4) Bytes are kept as the program holds them, with no host code-page conversion
  (IBM says TEXT is "copied unchanged"; the conversion only happens on a SEND). **Refused by name**: FROM and FROMDOC (the
  retrieved-document format and its embedded tags, and the template language run over it), SYMBOLLIST / LISTLENGTH /
  DELIMITER / UNESCAPED (the symbol table), DOCSIZE (the size CICS counts, tags included), HOSTCODEPAGE / CHARACTERSET /
  CLNTCODEPAGE (code pages), a RETRIEVE without DATAONLY (the tags CICS embeds are not laid out) or without MAXLENGTH (no
  stated default), a CREATE of TEXT / BINARY without LENGTH (no stated default), a literal TEXT / BINARY / DOCTOKEN (the
  COBOL form takes a data area); at run time a template whose text holds symbols (`&name;`) or template commands (`#set`,
  `#include`, `#echo`), a LENGTH past the TEXT / BINARY area and a document longer than INTO that MAXLENGTH lets through
  (CICS reads or writes the storage that follows, which GnuCOBOL lays out unlike IBM's compiler: X6), and templates the run
  does not state. DOCUMENT INSERT / SET / DELETE stay refused whole: no corpus program uses them.
- **Not modelled / unobserved**: a document built from several parts (INSERT, bookmarks), the symbol table and the template
  language, code-page conversion, a document kept past its task. No cics-crucible case proves it yet: the crucible's case
  format has no way to state the installed template text (a SPEC change, a separate PR in that repository).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven on `CicsTask` and the stub C
  (tests/cics_crucible/test_cics_runtimes.py: both answer alike); the translators' refusals are tested in
  tests/cobol_mainframe/test_det_translate.py and test_equivalence_cics.py. All ten DOCUMENT statements of zECS's
  ZECS000 / ZECS001 / ZECS003 translate (no DOCUMENT hole is left in the det survey); those programs stay held by WEB.

## Language Environment

### L1. CEEDAYS — MATCHED where documented, REFUSED otherwise
- **Modelled.** Pictures `YYYY-MM-DD` (and its `/` and `.` forms) only.
- **Refused (exit 98).** A picture inside a longer field (CardDemo's `'YYYYMMDD  '`) and a numeric month outside
  1–12, because IBM documents neither 2508 vs 2517 nor how trailing blanks are read.
- COACTUPC's cursor placement after its date fields is unreached until z/OS settles it.

### L2. CEE3ABD — MATCHED
- `ggabend.c` records `ABEND Unnnn`, and the Java side's CobolAbend gives the same.

### L3. WORKING-STORAGE with no VALUE clause — ASSUMED
- **What.** GnuCOBOL initialises such an alphanumeric item to spaces. On z/OS its first contents follow the LE
  runtime option STORAGE (commonly binary zeros, or whatever the storage held): the program's source does not say.
- **Where it shows.** CBACT01C moves the 10-byte `CODATECN-0UT-DATE` to `OUT-ACCT-REISSUE-DATE`, but COBDATFT (A1)
  writes only its first 8 bytes and `CODATECN-REC` has no VALUE clause. The last 2 bytes of each OUTFILE record's
  reissue date are GnuCOBOL's spaces, and the Java side writes the same.
- **Where it shows (CBSA, #4270).** CRDTAGY1-5's `WS-CONT-IN` (261 bytes, no VALUE clause) is filled by GET CONTAINER
  INTO; a container shorter than 261 bytes (scenario `container-short`) leaves the rest as it started, and PUT
  CONTAINER writes all 261 bytes back: GnuCOBOL's spaces in the alphanumeric items and its zeros in the unsigned
  numeric DISPLAY items (date of birth, review date), the same bytes on the Java side.
- **Assumed** to be spaces (zeros for a numeric DISPLAY item, as GnuCOBOL initialises it). A z/OS run with
  STORAGE(00) would give X'0000' there.

## Assembler routines

### A1. COBDATFT — MATCHED where the source decides, REFUSED otherwise
- **What.** CardDemo's date routine `app/asm/COBDATFT.asm` (S/370 assembler), CALLed by CBACT01C. GnuCOBOL cannot run
  it, so the harness runs a translation of it, instruction for instruction: `tests/equivalence/le/cobdatft.c` for the
  COBOL side and the det runtime's `Cobdatft.java` for the Java side, the same bytes on both.
- **Modelled.** Input type `'2'` (YYYY-MM-DD) to output type `'2'` (YYYYMMDD): `COOUTDT(4) = COINPDT(4)`,
  `COOUTDT+4(2) = COINPDT+5(2)`, `COOUTDT+6(2) = COINPDT+8(2)`; every other byte is left as it was (see L3); R15 = 0.
- **Refused (exit 98).** Input type `'1'`: its `CLC COINPDT+4,=C'-'` has no explicit length, so it compares 20
  bytes against a 1-byte literal and whatever the literal pool holds after it. The error path: an `MVC` of 38 bytes
  from a 13-byte literal. What both do depends on the load module, not the source, so no proof rests on them.
  CBACT01C never takes either.

## Db2 (`equivalence_sql.py`, `ggsql.c`, `DetSql`)

### Q1. Db2 for Linux, not z/OS — ASSUMED
- **What.** Both sides run their SQL on Db2 Community Edition (Db2 for LUW). The SQLCODEs these programs meet from Db2 (0, +100,
  -803, -811, -532) are the same codes on z/OS. SQLERRMC tokens come from Db2 itself.
- **Not compared to z/OS.** SQLSTATE subclasses, SQLERRD values beyond the row count, SQLERRP, and the dialect
  differences of other statements.

### Q1a. A binary host variable takes what its bytes hold — MATCHED (#4579)
- **What.** SELECT INTO / FETCH INTO a COMP / COMP-4 / BINARY / COMP-5 host variable gives SQLCODE -304 only for a value
  outside its halfword / fullword / doubleword (Db2 types the host variable by its data type: S9(9) COMP is INTEGER), not
  beyond its PICTURE's digits: 2147483647 into `S9(9) COMP` is assigned. That holds under TRUNC(STD) too; STD limits
  COBOL's own MOVE / arithmetic (C1), not the SQL assignment. ggsql.c `num_store` and DetSql (`Cobol.storeHostChecked`) agree.

### Q1b. A datetime host variable Db2 rejects: -180 / 22007 on both sides — MATCHED (#4658)
- **What.** An UPDATE binding an unset (non-date) PIC X host variable to a DATE column gets SQLCODE -180, SQLSTATE 22007
  ("the string representation of a datetime value is not valid") from Db2 for LUW, and the same on z/OS Db2 (-180 is the
  documented SQLCODE for this, SQLSTATE 22007). IBM's JDBC driver refuses some such values on the client with its own
  -4220 (conversion error) before Db2 sees them; that code is never a Db2 SQLCODE an embedded-SQL program meets, so
  DetSql maps it to -180 / 22007. Other driver errors pass through unchanged. SQLERRMC/SQLERRD of the mapped error stay
  empty (the DISPLAYed SQLERRD(3) is 0 on both sides).

### Q2. EXEC SQL keeps RETURN-CODE — ASSUMED
- The precompiled CALL preserves RETURN-CODE around the stub. Whether IBM's DSNHLI call resets it is not documented.

### Q3. The Db2 unit of work — MATCHED for CICS tasks and for batch steps (#4269)
- **CICS.** The equivalence test runs each task's SQL in one Db2 transaction, as CICS's Db2 thread does: committed when
  the task ends, rolled back with the task's recoverable files by SYNCPOINT ROLLBACK or an abend (X3). The transaction
  is the harness's (`equivalence_cics.py`, a `TransactionTemplate` around the task); a deployment must give each task
  the same unit of work. Reached: CBSA XFRFUN's four ROLLBACK paths are proven.
- **CICS, SQL after a SYNCPOINT ROLLBACK (#4270).** IBM: SYNCPOINT ROLLBACK ends the unit of work and the task's next
  recoverable change starts a new one, committed when the task ends. The Java side rolls the task's Db2 connection back
  at the SYNCPOINT ROLLBACK and goes on in the same transaction, so the SQL that follows is committed with the task, as
  the COBOL side's Db2 commits it. Reached: CBSA INQACCCU's cursor failing inside CREACC's task (its SYNCPOINT
  ROLLBACK, then CREACC's CONTROL updates and INSERTs: cbsa-creacc, cbsa-bnk1cac). A recoverable FILE changed after a
  SYNCPOINT ROLLBACK is still undone with the task on the Java side (the transaction is marked rollback-only): no case
  reaches one, and it would show as a difference.
- **CICS, EXEC SQL COMMIT / ROLLBACK.** IBM: both are invalid under CICS -- Db2 for z/OS answers -925 / -926 (SQLSTATE
  2D521; Db2 for z/OS Codes) and the task's unit of work is CICS's (SYNCPOINT). The det translator REFUSES a CICS
  program's ROLLBACK by name. A CICS program's COMMIT stays a reset of the SQLCA on the Java side and a real commit on
  the oracle (Db2 for Linux has no CICS attachment): DIFFERS from z/OS's -925, declared; no burned CICS program
  issues one (CBSA's COMMIT WORK is in BANKDATA, a batch program). Next slice: -925 / -926 on both sides.
- **Batch (#4269).** A batch step is one Db2 unit of work, as Db2 for z/OS runs a program under DSN (TSO) or CAF:
  a commit point at each COMMIT and at the program's normal end; an abnormal end backs out the work since the last
  commit point (Db2 for z/OS Application Programming and SQL Guide, "Unit of work in TSO" / "Making changes to
  data: commit and rollback"). EXEC SQL COMMIT [WORK] commits and closes every cursor not declared WITH HOLD (a held
  one stays open, positioned before its next row); ROLLBACK [WORK] backs out and closes every cursor, held or not
  (Db2 for z/OS SQL Reference, COMMIT statement and ROLLBACK statement); a FETCH or CLOSE of a cursor so closed is
  -501. COMMIT / ROLLBACK with other options are REFUSED by name.
  - **Savepoints.** SAVEPOINT name [UNIQUE] ON ROLLBACK RETAIN CURSORS, ROLLBACK [WORK] TO SAVEPOINT [name] and
    RELEASE [TO] SAVEPOINT name (SQL Reference, SAVEPOINT / ROLLBACK / RELEASE SAVEPOINT) run as written on the
    unit of work's connection on both sides (DetSql.savepoint; the precompiler makes each an EXEC), so Db2 itself
    answers them: -880 for a savepoint that does not exist or was released, -881 for a UNIQUE one set again. The
    cursors stay open (RETAIN CURSORS is required). A host variable in one, or one in a CICS program, is REFUSED.
    Oracle instrument quirks, measured and neutralised: IBM's CLI runs `ROLLBACK WORK TO SAVEPOINT x` as a ROLLBACK
    of the whole unit of work (answering 0 where Db2 answers -880), so the precompiler drops the noise word WORK;
    CLI's row count -1 for a statement with none no longer reaches SQLERRD(3), which stays 0 as on z/OS.
  - **The det port.** DetSql.commit / rollback end the unit of work the runner gives (DetSql.unitOfWork); with none
    given, each statement commits as it runs: COMMIT has nothing more to commit and ROLLBACK is refused at run time
    (UnsupportedOperationException), never answered. The equivalence test runs the step in one transaction on the
    harness's Db2 and gives DetSql its connection; a deployment must give each step the same unit of work.
  - **The oracle.** ggsql.c runs with autocommit off and commits at a normal exit; ggabend.c (CEE3ABD) now backs the
    unit of work out before the process ends. Db2 for Linux's CLI keeps every cursor open across a commit
    (SQL_ATTR_CURSOR_HOLD defaults on) and leaves the handle of one a rollback closed: ggsql.c closes them itself as
    z/OS does (the precompiler marks a WITH HOLD cursor's OPEN `H` in the statement table). MATCHED to z/OS by
    construction; a libcob run-time failure that is not CEE3ABD still commits at exit (never compared equal: the
    Java side's exception is an UNCODED abend).
  - **Compared.** After an abend both sides' Db2 tables are now compared (they hold what the step committed); the
    statement outcomes (#4507) leave out COMMIT / ROLLBACK and a FETCH / CLOSE of a cursor they closed (-501 is the
    stub's, not Db2's).
  - **Reached.** No burned program issues EXEC SQL ROLLBACK (#4269 census: NEND-DAY / NINT-CALC, non-burned, are
    the programs it unblocks), so a synthetic estate pins it: `tests/equivalence/db2/uow` (UOWDEMO, traced by hand;
    `tests/cobol_mainframe/test_sql_unit_of_work.py`, EQUIVALENCE_E2E=1) -- a commit, two changes backed out, -803
    then ROLLBACK, a cursor closed by COMMIT, a WITH HOLD cursor kept by it and closed by ROLLBACK, a savepoint (the
    insert after it backed out, a rollback to it once released -880), work uncommitted at a normal end (kept) and at
    an abend (backed out). Proven on both sides: SYSOUT, the table, and every statement's SQLCODE / SQLSTATE / rows.

### Q4. Unsupported embedded SQL — REFUSED
- **Refused.** WHENEVER, dynamic SQL (PREPARE / EXECUTE / DESCRIBE), CONNECT, CALL, ALLOCATE / ASSOCIATE, SCROLL
  cursors, host-variable arrays and a host variable in a savepoint statement (Q3) stop the precompiler and the det
  translator by name (and a savepoint statement in a CICS program the det translator), as does an undeclared host
  variable or a `WHERE CURRENT OF` a cursor the program does not declare. A positioned UPDATE / DELETE on a declared
  cursor runs (Q8).

### Q5. DSNTIAC / DSNTIAR — REFUSED
- **What.** Db2's message formatters (DSNTIAR formats an SQLCA into message text in a caller's buffer; DSNTIAC is its CICS
  interface; IBM Db2 for z/OS Application Programming and SQL Guide, paraphrased and not re-fetched for this entry) are not modelled: the text is Db2's message catalogue, which IBM documents by message number but
  not byte for byte, and the oracle (ggsql.c / equivalence_sql.py, Db2 for Linux) has no routine that produces
  z/OS's text. The port refuses both by name, whether the program writes `CALL 'DSNTIAC'` or calls it through a data
  item (COTRTLIC's `CALL LIT-DSNTIAC`, #4736): "DSNTIAC: Db2's message text is not modelled".
- **Reached.** No scenario reaches it. COTRTLIC's call, on the Db2-error path, is its one untranslated statement.

### Q6. Date text and DDL from z/OS jobs — ASSUMED
- **Date text.** A DATE column read into a character host variable comes back as `YYYY-MM-DD` on both sides: Db2's
  CLI and IBM's JDBC driver convert dates to ISO text. On z/OS the form is the bind's `DATE` option, else the
  installation default (ISO as IBM ships it). CBSA's bind names none; a site with `DATE(EUR)` or `DATE(USA)` would
  hand CBSA's `YYYY-MM-DD` slicing other text.
- **In SQL text, not ISO.** The harness database's own default is USA: `CHAR(date)` inside a statement gives
  `10/01/2026`. No proven statement formats a date in SQL.
- **Input.** `DD.MM.YYYY` (CBSA's PROCTRAN dates) is accepted on input by both, whatever the option.
- **DDL from a job.** `equivalence_db2.ddl_text` runs a z/OS job's in-stream SQL with the placement and audit clauses
  removed (`IN db.ts`, `USING STOGROUP`, `AUDIT`, `[NOT] VOLATILE CARDINALITY`, `SET CURRENT SQLID`, CREATE
  DATABASE / STOGROUP / TABLESPACE). None changes what a query returns. The bind's `QUALIFIER` is each side's
  current schema.

### Q7. `CCSID EBCDIC` tables — DIFFERS
- **What.** GenApp's DDL creates its tables `CCSID EBCDIC`; Db2 for Linux has no such clause, and the harness
  database is Unicode. A table's text then sorts in Unicode order, not EBCDIC order, so `ORDER BY` on text and text
  ranges (`BETWEEN`, `>`) can differ from z/OS for mixed letters and digits (as D1 for the programs).
- **Reached.** No proven statement orders or ranges on text that mixes letters and digits.

### Q8. Positioned UPDATE / DELETE — MATCHED
- **COBOL side.** The statement runs as written: the CLI names each cursor at OPEN (`SQLSetCursorName`).
- **Java side.** A generated repository has no live cursor, so a `FOR UPDATE` cursor's query also returns each row's
  `RID_BIT` (as `GG_RID`, never assigned to a host variable), and the positioned statement updates `WHERE
  RID_BIT(table) = :ggRid` for the row FETCH last returned; no current row is -508, as Db2 gives.
- `RID_BIT` is Db2 for Linux's; a production target on Db2 for z/OS would use `RID()` or the table's key.

### Q9. More host variables than columns — MATCHED
- GenApp's LGUPDB01 FETCHes six host variables from a five-column cursor (a GenApp defect). Db2 sets SQLWARN3 and
  leaves the sixth as it was; both sides now do the same (the COBOL stub had reported an error, the Java side a
  NULL).

### Q10. A statement the driver fails with no Db2 SQLCODE — REFUSED (#4270)
- **What.** A host variable Db2 cannot take (GenApp LGAPDB01's INSERT COMMERCIAL with a blank CA-LASTCHANGED as its
  REQUESTDATE, reached when the SELECT LASTCHANGED before it is faulted) fails in the client: Db2's CLI gives its own
  native code -99999 (SQLSTATE 22007), IBM's JDBC driver its own -4220. What Db2 for z/OS answers is not known here,
  so the COBOL stub stops the task by name ("the CLI failed it in the client") instead of passing -99999 on as an
  SQLCODE: an enumerated fault task (M2) that reaches it is not judged; a declared scenario stops the case.

## The Java side

### J1. Files on H2 — ASSUMED
- **What.** The proofs run the generated project's `h2` target: VSAM files become H2 tables read through the entities'
  record codecs, and Db2 repositories run on the real Db2.
- **Not proven.** Another target database (Postgres, Oracle) brings its own collation and type behaviour.

## Method

### M1. The scenarios are ours — limits every claim
- **Sources.** The inputs come from the corpora's data, from `@generate` (records built from each copybook's layout,
  edge values per PICTURE) and from scenarios written by us or by a model reading the COBOL, then strengthened from
  mutation survivors (`tests/tools/strengthen.py`).
- **What a proof covers.** The paths its coverage figure reports, and nothing else. CardDemo, CBSA and GenApp are
  public development estates; a fresh estate is measured through `tests/tools/trial.py`.

### M2. SQL faults — injected since #4173 (the SQLCA ASSUMED)
- **How.** A statement is named by its program and the line of its EXEC SQL in the file it is written in (an INCLUDEd
  member's own line); the det port's DetSql calls carry the same key. A fault plan (`PROGRAM LINE NTH SQLCODE
  SQLSTATE`) makes that execution skip Db2 on both sides (ggsql.c, DetSql) with that SQLCODE and SQLSTATE, and both
  log it; a run is proven only if the same faults fired on both sides. A scenario declares `sql_faults` (by `line`, or
  by `table` and `verb`); `equivalence.py run --sql-faults auto` (the default) adds one task per statement the case's
  tasks executed, its first execution failing: -803 for an INSERT, +100 for a SELECT INTO, -913 for an UPDATE, DELETE,
  OPEN or FETCH. COMMIT, CLOSE and `SET :H = VALUES` get none.
- **Assumed.** The SQLCA a fault leaves is reset's: SQLCODE and SQLSTATE set, SQLERRMC empty (SQLERRML 0), SQLERRD
  zero, no warnings. z/OS sets message tokens (-803's index, -913's resource) a program could DISPLAY. -913 rolls back
  the statement only; -911's unit-of-work rollback is not used. Nothing else changes: no row, no host variable, a
  cursor where it was.
- **Not judged.** A fault task that LINKs to a program the case does not run is judged up to that LINK (X6). One whose
  path reaches a det port's named hole (COTRTLIC's CALL DSNTIAC) is recorded "not judged" and left out of the proof
  and of the coverage figure. A port without DetSql (a model port) cannot take a planned SQL fault: such a task is
  recorded "not judged" (no SQL fault hook), never run unfaulted.
- **Effect.** Coverage of the 17 Db2 cases before and after is in the #4173 PR, e.g. GenApp LGACDB01 6/14 → 8/14
  branches, LGUPDB01 17/38 → 26/38, CBSA DELACC 10/14 → 13/14.

### M3. A LINKed program's COMMAREA — fixed 2026-10-02
- A LINKed program answers through the COMMAREA it leaves in its caller's storage. Until 2026-10-02 the harness
  compared such a program's files and tables but not that COMMAREA, so CBSA's and GenApp's result codes (COMM-SUCCESS,
  CA-RETURN-CODE) went unchecked.
- A case marked `"linked": true` now compares it after every task that does not abend. All 7 earlier LINKed cases
  re-proved with it.

### M4. Clock fields — declared
- **What.** A value the program takes from the system clock (Db2's `CURRENT TIMESTAMP`: GenApp LGUPDB01 sets
  `POLICY.LASTCHANGED` and reads it back into its COMMAREA) cannot be equal across two runs made at different times.
- **The rule.** A case names its clock fields (`"clock_fields"`: table columns, COMMAREA fields or slices of them).
  Such a value is compared as what it is -- a well-formed timestamp the run wrote, within the last day -- not by its
  digits. A value from the seed or the scenario is still compared exactly. Every masked value is counted in the
  report (`clock_masked`).
- This is the first declared difference (#4051) of its kind: narrow, named in the case, and reported where used.

## What would settle most of this

**One session on a z/OS system** with Enterprise COBOL 6.x, LE, CICS TS and Db2 for z/OS, running:

- a binary-truncation and arithmetic-intermediate table (C1, C2, C3, C4);
- a collation probe (D1);
- CEEDAYS with the refused inputs (L1);
- a DSNHLI RETURN-CODE check (Q2);
- one CardDemo transaction's 3270 stream (X2).

Each answer becomes either a model that matches (MATCHED) or a declared difference with a person's approval (#4051).

## Keeping this page true

- **A new model** (a stub, a shim, an LE service) adds its entry here in the same PR, with its status.
- **A refusal or a declared difference** found in the code (`not modelled`, `Unsupported`, `UnsupportedOption`) has
  an entry here.
- **A change of status** (a z/OS run, a new flag) edits the entry and its date. The summary table follows (it is generated from the entries' front matter).
- **How.** This page is generated; do not edit it. Each entry is one file, `docs/language_status/register/<ID>.md`
  (front matter: id, family, status, title, area, summary, reached; then the entry text). Take a new ID with
  `python tests/tools/register.py next <family>` when the issue is filed, so parallel PRs never pick the same number
  (`new <ID>` writes a skeleton). Prose sections live in `register/_parts/`, the page order in `register/_layout.json`.
  Then `python tests/tools/register.py render`; CI runs `register.py --check` and fails on a stale page.
