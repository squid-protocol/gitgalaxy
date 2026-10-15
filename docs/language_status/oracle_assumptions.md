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

The COBOL side's driver tarball is pinned too (#4980): `tests/equivalence/odbc_cli.pin` holds IBM's URL and its sha256.
`equivalence_db2.fetch_odbc_cli()` downloads it with `curl --retry`, CI caches it on the pin, and the Dockerfile COPYs it
and checks the sha256 again; a failed download or a mismatch is reported as infrastructure, never as a case failure.

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
| F5 | files | a key item that is not in a record of its own FD (WORKING-STORAGE, another file's record) is refused by name; GnuCOBOL does not compile it either (#4804) | REFUSED (key outside the record) | — |
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
| X17 | CICS | Channels and containers: PUT / GET / DELETE CONTAINER, LINK / XCTL CHANNEL, ASSIGN CHANNEL; bytes never converted; CCSID options, SET, BYTEOFFSET, RETURN CHANNEL refused (MOVE and the browse: X42) | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible ca-channel-containers, unreleased) |
| X18 | CICS | Interval control on the det port: START (INTERVAL / TIME / AFTER / AT, TERMID, REQID, PROTECT, FROM, RTRANSID / RTERMID / QUEUE, CHANNEL), RETRIEVE (INTO / LENGTH, the data options, ENVDEFERR), CANCEL REQID, RUN TRANSID CHILD [CHANNEL], FETCH ANY / CHILD (NOSUSPEND, TIMEOUT or waiting), FREE CHILD, and DELAY as the wait that dispatches RUN children (#4950); the child schedule, TIME RESP2 and the order of out-of-range checks assumed; ties, a child's region-resource commands, RETRIEVE SET / WAIT refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible gt-start-retrieve, gt-terminal-coalesce, gt-start-options, unreleased) |
| X19 | CICS | ASSIGN on the det port: STARTCODE (TD / S / SD), USERID (the default user), FACILITY / SCRNHT / SCRNWD (INVREQ RESP2 5 without a terminal) from facts the harness states; no data area written when ASSIGN raises INVREQ; OPID, NETNAME, TERMCODE, FCI, the other screen sizes, work-area lengths and the rest refused | ASSUMED (REFUSED where the harness cannot decide) | yes (cics-crucible gt-assign-startcode, unreleased) |
| X20 | CICS | SEND TEXT on the det port and the stub: TERMINAL accepted as the default output disposition (the principal facility; the event is that of SEND TEXT without it); ACCUM, PAGING, SET, REQID, HEADER, TRAILER, JUSTIFY / JUSFIRST / JUSLAST, the printer, partition and LDC options, MSR, FMHPARM, DEFAULT / ALTERNATE refused | MATCHED (REFUSED where the region cannot decide) | yes (cics-crucible gt-send-text-terminal, unreleased) |
| X21 | CICS | EIBTASKN: the task's number is a stated fact of the run (`$GGCICS_TASKN` / `CicsTask.withTaskNumber`, a case's or scenario's `"taskn"`, default 0), not the number CICS assigns; a value outside 0 to 9,999,999 refused | DIFFERS (the value) / MATCHED (both sides) | yes (every CICS task; read by CBSA's Db2 programs, GenApp LGICDB01) |
| X22 | CICS | READ GTEQ / GENERIC on a KSDS: the first record whose key (or its first KEYLENGTH bytes) equals RIDFLD's or, with GTEQ, is greater, in the browse's key order (D1); NOTFND RESP2 80; READ UPDATE holds the record found; RIDFLD not updated; #4771: on a file named at run time the full key is that file's (looked up then), and DELETE GENERIC deletes every record with the generic key (NOTFND RESP2 80 when none); a GENERIC KEYLENGTH not shorter than the key or not above zero, a non-constant KEYLENGTH and a RIDFLD shorter than the key searched refused | ASSUMED (REFUSED where IBM is silent or the layout decides) | yes (GenApp LGICVS01 genapp-lgicvs01) |
| X23 | CICS | A COMMAREA of a stated length (a scenario's `commarea_length`, EIBCALEN shorter than the record): the program is given exactly those bytes; a reference past EIBCALEN refused on both sides, the task judged up to it | ASSUMED (REFUSED past EIBCALEN) | yes (GenApp LGACDB01, LGACDB02, LGDPDB01, LGIPDB01) |
| X24 | CICS | A task started with a channel (a scenario's `channel`: what a RUN TRANSID CHANNEL parent or a LINK CHANNEL caller passed), made its first program's current channel; the containers left on that channel compared at the task's end (dropped on an abend), byte for byte; RUN TRANSID children not run | ASSUMED | yes (async credit-card CRDTCHK, CSSTATS2, CSSTATUS, GETADDR, GETNAME; CBSA CRDTAGY1-5, an explicit CHANNEL(CIPCREDCHANN)) |
| X25 | COBOL layout | SYNCHRONIZED slack bytes in the layout model (GalaxyIR `record_layout`, `_storage_spans`): IBM Enterprise COBOL boundaries (halfword up to 4 digits, fullword above, the 8-byte binary S9(10)-S9(18) included; COMP-1 / INDEX / pointers fullword; COMP-2 doubleword) counted from the record, the table slack of IBM's rule; GnuCOBOL / Micro Focus may align an 8-byte binary on a doubleword | ASSUMED (IBM's fullword; z/OS is the target) | no (no committed case reaches an 8-byte SYNC binary) |
| X26 | CICS | BIF DEEDIT FIELD [LENGTH] edited in place in the region's EBCDIC page (CCSID 037); INQUIRE / SET TERMINAL UCTRANST as the CVDAs UCTRAN 450 / NOUCTRAN 451 / TRANIDONLY 452, the terminal's value stated by the run (the case TYPETERM's UCTRAN), a terminal RECEIVE after a SET refused; DFHVALUE(name) in the stub's programs is IBM's CVDA number; a DEEDIT field with no digit left, beyond 7-bit ASCII or past LENGTH, and the UCTRANST of a terminal other than the task's, refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-deedit-uctranst, unreleased; CBSA BNK1DCS's UCTRANST store / restore and the BNK1 screens' DEEDIT: cbsa-bnk1dcs, cbsa-bnk1cac ...) |
| X27 | CICS | RETURN TRANSID ... IMMEDIATE: the task of TRANSID attached at once with the COMMAREA, ahead of any terminal input and any START request, the terminal's next operator step left alone; its EIBAID is not stated by IBM (the crucible runner gives none and a case never reads it), its STARTCODE TD; INVREQ RESP2 1 (no terminal), INVREQ RESP2 2 (below the highest level), LENGERR RESP2 11 return to the program; LINK ... SYNCONRETURN accepted and ignored (IBM: "ignored if the link is local"); IMMEDIATE without TRANSID, and both INVREQs at once (no terminal below level 1), refused | ASSUMED (the STARTCODE; REFUSED where IBM is silent) | yes (cics-crucible pc-return-immediate, unreleased; CBSA BNKMENU and the BNK1 screens' PF3, the task's terminal a case's `"termid"`: cbsa-bnkmenu, cbsa-bnk1cac ...) |
| X28 | CICS | FORMATTIME with RESP / RESP2: INVREQ RESP2 1 for an ABSTIME below zero, nothing formatted (without RESP the INVREQ's handling is refused at run time); ASKTIME with NOHANDLE and without ABSTIME (EIBDATE / EIBTIME as dispatched, X4); READQ TS ... LENGTH(LENGTH OF area): the most INTO takes, LENGERR truncation, no length stored back; RECEIVE MAP ... ASIS: input delivered as typed, lower case kept; an ABSTIME that is not packed decimal (the port reads the field by its declared usage), STRINGFORMAT (RESP2 2) and the output areas of an INVREQ FORMATTIME not modelled / not read | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-resp-options, unreleased) |
| X29 | CICS | INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID / ODUSERID / ODFACILNAME / ODNETWORKID / ODFACILTYPE: the task's own origin data, the five values the run states (a case's `origin`, for a task terminal input started; unstated, refused), the facility type as IBM's CVDA, a command with no origin option refused (INVREQ RESP2 2 is ambiguous); DELETEQ TS: the whole queue and its READQ NEXT position, QIDERR, INVREQ for a name of binary zeros, RESP2 0; QUERY COUNTER (COUNTER / POOL / VALUE): the value left unchanged, INVREQ RESP2 201 for a counter that is not there, a value beyond a fullword, MINIMUM / MAXIMUM / NOSUSPEND, a task number other than EIBTASKN and the origin of a task not started by terminal input refused; RECEIVE MAP ... TERMINAL: the task's terminal, as every RECEIVE MAP | ASSUMED (REFUSED where IBM is silent) | INQUIRE ASSOCIATION, DELETEQ TS, RECEIVE MAP TERMINAL: yes (cics-crucible hc-inquire-deleteq, unreleased; INQUIRE ASSOCIATION and RECEIVE MAP TERMINAL also CBSA BNK1CRA / BNK1DCS: cbsa-bnk1cra, cbsa-bnk1dcs, a case's `"origin"`); QUERY COUNTER: no (the reference region has no named counters; unit tests on both runtimes) |
| X30 | CICS | DEFINE COUNTER (COUNTER / POOL / VALUE; none: the initial value zero; a counter that exists: INVREQ RESP2 202; a pool or counter name outside IBM's characters: INVREQ RESP2 403 / 404) and DELETE COUNTER (a counter that is not there: INVREQ RESP2 201; a pool outside IBM's characters: 403); GET COUNTER and QUERY COUNTER answer INVREQ RESP2 201 for a counter that is not there (GET COUNTER answered NOTFND before: IBM lists none) and 403 / 404 for a bad pool / name; MINIMUM / MAXIMUM / NOSUSPEND / DCOUNTER, a VALUE below zero and a counter name of blanks refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-named-counters, unreleased) |
| X31 | CICS | SEND MAP / RECEIVE MAP for a map its mapset does not hold (MAPSET omitted: IBM defaults it to the MAP name, so `SEND MAP('BNK1CCM')` looks for map BNK1CCM in mapset BNK1CCM): abend ABM0, the transaction terminated, no condition raised (RESP / RESP2 / HANDLE CONDITION do not see it; a HANDLE ABEND exit does), recorded as an ABEND event with cause `system` | ASSUMED (REFUSED where IBM is silent: the mapset itself undefined, a non-constant name) | yes (cics-crucible hc-map-not-in-mapset, unreleased) |
| X32 | CICS | INQUIRE URIMAP's browse (START / NEXT / END with URIMAP, PATH, TRANSACTION: END RESP2 2 past the last definition, ILLOGIC RESP2 1 for a START while one is open; the installed definitions and their order are stated by whoever runs the task; a short value is padded with blanks; the areas are left alone on any condition other than NORMAL) and WRITE OPERATOR (TEXT only; recorded as a WRITE-OPERATOR event); the direct form INQUIRE URIMAP(name) (modelled since #4768, X34), every other URIMAP attribute, a NEXT / END with no browse, and a console text IBM reformats (DFHnnnn / DFHaannnn, or over 113 characters) refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible gt-urimap-browse, unreleased) |
| X33 | CICS | DOCUMENT CREATE (DOCTOKEN; none, TEXT / BINARY with LENGTH, or TEMPLATE: an empty document, the area's bytes unchanged, or the text the installed DOCTEMPLATE yields; LENGERR RESP2 1 for a negative LENGTH, NOTFND RESP2 3 for a template not installed) and DOCUMENT RETRIEVE (DOCTOKEN, INTO, LENGTH, MAXLENGTH, DATAONLY: at most MAXLENGTH bytes INTO, LENGTH the document's length, LENGERR RESP2 2 when truncated, NOTFND RESP2 1 for an unknown token, LENGERR RESP2 1 for a negative MAXLENGTH); the DOCTOKEN value, the installed templates' text, and the text a retrieved document's bytes are in are ours / stated by whoever runs the task; FROM, FROMDOC, SYMBOLLIST / LISTLENGTH / DELIMITER / UNESCAPED, DOCSIZE, HOSTCODEPAGE / CHARACTERSET, a RETRIEVE without DATAONLY or MAXLENGTH, a CREATE of TEXT / BINARY without LENGTH, a template with symbols or template commands, and DOCUMENT INSERT / SET / DELETE refused | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C; no cics-crucible case yet) |
| X34 | CICS | INQUIRE URIMAP(name) with no browse option reads that definition among the installed ones the run states (X32's list: PATH and TRANSACTION as a browse NEXT returns them, NOTFND RESP2 3 when it is not installed, a browse in progress left where it was); INQUIRE PROGRAM STATUS answers ENABLED (CVDA 23), the DEFINE PROGRAM default, for every program the region defines, on NORMAL only; a case CSD defining a program STATUS(DISABLED) refused | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C; no cics-crucible case yet) |
| X35 | CICS | The HTTP server is a stated fact (http_peers: scheme, host, port, CLIENT URIMAP and path, and the response to each request, matched by method, path and query in order); WEB OPEN by URIMAP or HOST / HOSTLENGTH / PORTNUMBER (80 / 443 when omitted) / SCHEME returns our 8-byte token (GGWSnnnn), LENGERR 21, INVREQ 40 / 138; WEB CONVERSE sends METHOD, PATH (the URIMAP's when omitted), QUERYSTRING, FROM with MEDIATYPE, recorded as a WEB-CONVERSE event, and returns INTO (at most MAXLENGTH, INTO's length when omitted; LENGERR 57 when longer), TOLENGTH, STATUSCODE, the reason phrase's bytes and MEDIATYPE (blank-padded to 56), with NOTOPEN 27, INVREQ 33 / 34 / 54 / 76, LENGERR 5 / 8 / 16 / 50 / 59; WEB CLOSE NOTOPEN 27; the exchange is in the program's characters (conversion options change nothing); refused: an unstated peer or response, two conditions at once, TRACE / OPTIONS, MAXLENGTH 0, no PATH on a HOST session, a blank MEDIATYPE with a body, a reason phrase longer than STATUSLEN, a length past its area, and every option zECS does not use | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C, which answer one step list alike; no cics-crucible case yet) |
| X36 | CICS | WEB PARSE URL is pure: URL / URLLENGTH are split into SCHEMENAME (upper case, blank-padded to its 16-byte area), HOST / HOSTLENGTH, PORTNUMBER (explicit, else 80 for HTTP and 443 for HTTPS), PATH / PATHLENGTH (with its leading slash) and QUERYSTRING / QUERYSTRLEN (without its question mark, still escaped); each length option is read as the area's size and set to the piece's length; INVREQ 28 (no scheme and ://, an empty scheme or host, a port that is not 1-5 digits or above 65535: ASSUMED) and INVREQ 65 (a percent not followed by two of 0-9 A-F); the areas are written on NORMAL only; refused: a scheme other than HTTP / HTTPS, user-info, a fragment, an IPv6 host, an empty port or port 0, a lowercase hex digit in an escape, a URLLENGTH not above zero or past its area, LENGERR (host / path / query longer than its length), a length past its area, a PATH or QUERYSTRING asked for when the URL has none, two conditions at once, HOSTTYPE | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C, which answer one step list alike; no cics-crucible case: the command writes no event) |
| X37 | CICS | The task serves one inbound HTTP request that whoever runs it STATES (http_request: scheme, host, port, method, version, path, query, headers, media type and body; unstated, WEB SEND is refused); WEB SEND FROM / FROMLENGTH, DOCTOKEN or CONTAINER [CHANNEL] with ACTION(IMMEDIATE), ACTION(EVENTUAL) or no ACTION, MEDIATYPE, STATUSCODE (200 when omitted), STATUSTEXT / STATUSLEN (the whole area when STATUSLEN is omitted), SRVCONVERT / NOSRVCONVERT and, for a document, DOCSTATUS(DOCDELETE | NODOCDELETE) is recorded as a WEB-SEND event (status, reason phrase or none, media type or none, body, action) and compared; an IMMEDIATE response is recorded when sent, an EVENTUAL one (and an omitted ACTION, IBM's default for a send that is not chunked) is held and recorded once at the end of the task, after the task's other events, a second EVENTUAL send replacing the first (the whole response: ASSUMED); DOCDELETE deletes the document once its contents are saved (a later request for it is NOTFND 1), NODOCDELETE (the default) keeps it; INVREQ 11 (an action that is neither IMMEDIATE nor EVENTUAL), INVREQ 72 (204 / 205 / 304 with a body), INVREQ 143 (an invalid DOCSTATUS), NOTFND 1 (a DOCTOKEN that names no document: not created, deleted or wrongly named); for a container body CONTAINERERR 2 (no such container), CHANNELERR 2 (no such channel), INVREQ 145 (no CHANNEL and no current channel), INVREQ 150 (SRVCONVERT on a DATATYPE BIT container); the response is in the program's characters (conversion changes nothing); refused: no stated request, an empty container body, a BIT container sent without conversion, FROM, DOCTOKEN or CHUNKING together with CONTAINER, CHANNEL without CONTAINER, a second send after an IMMEDIATE one, an IMMEDIATE send after an EVENTUAL one, a task that ended in an abend with an EVENTUAL response held, a WEB WRITE HTTPHEADER after any send, DOCSTATUS on a FROM send, FROMLENGTH or STATUSLEN not above zero, a length past its area, a STATUSCODE outside 100-599, a blank or malformed MEDIATYPE, SRVCONVERT on a media type that is not text/*, two conditions at once, and CHUNKING, CHARACTERSET, CLNTCODEPAGE, HOSTCODEPAGE, CLOSESTATUS, LENGTH | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C, which answer one step list alike and record the same event; no cics-crucible case yet) |
| X38 | CICS | #4972: EXTRACT WEB is IBM's synonym of WEB EXTRACT (one table, one runtime call, the same answers and refusals); EXTRACT TCPIP reads the connection the run STATES (tcpip: client / server IPv4 address, the names the DNS knows, the port, the SSL type): CLIENTADDR / CADDRLENGTH, CLIENTNAME / CNAMELENGTH, SERVERADDR / SADDRLENGTH, SERVERNAME / SNAMELENGTH written as bytes with each length option set to the real length (areas on NORMAL only), CLIENTADDRNU / SERVERADDRNU (the address as a signed fullword), CLNTIPFAMILY / SRVRIPFAMILY (IPV4, 300), PORTNUMNU, SSLTYPE (SSL 1030 / NOSSL 1031 / CLIENTAUTH 1032 / ATTLSAWARE 1205); an area given with its length option missing or not above zero LENGERR RESP2 1; a client name the DNS does not know length 0, the area left alone, NORMAL; refused: no connection stated, an address that is not IPv4 dotted decimal (IPv6, CLNTADDR6NU / SRVRADDR6NU), an address number past a signed fullword, a SERVERNAME the connection does not state, a name or address longer than its length (LENGERR RESP2 3 / 4 / 6 / 7), PORTNUMBER (the character form), AUTHENTICATE, TCPIPSERVICE, PRIVACY, MAXDATALEN, a length past its area, two conditions at once. #4940: WEB READ FORMFIELD / QUERYPARM read the stated body form (application/x-www-form-urlencoded) / query string as name=value pairs joined by '&' (split at the first '=', only %XX unescaped), the name matched without case (IBM), two pairs of the name refused, NAMELENGTH / VALUELENGTH not above zero LENGERR RESP2 1, no data INVREQ RESP2 13, no such name NOTFND RESP2 1, a value longer than VALUELENGTH cut with LENGERR RESP2 5 and VALUELENGTH its real length; WEB STARTBROWSE / READNEXT / ENDBROWSE of HTTPHEADER, FORMFIELD, QUERYPARM keep a browse per kind (ILLOGIC RESP2 10 / 5 for a second start, INVREQ RESP2 43 / 13 for no headers / data, INVREQ RESP2 4 READNEXT / ENDBROWSE before a start, ENDFILE with RESP2 0 at the end, LENGERR RESP2 1 for a length not above zero with the browse left where it was, LENGERR RESP2 4 / 5 for a FORMFIELD / QUERYPARM name / value that does not fit, cut, the same pair returned again, lengths the real ones), a start name matched exactly (case-only or duplicate matches refused), a start that raises a condition starts no browse (ASSUMED); refused: the code-page options, the client form (SESSTOKEN), HTTPHEADER truncation on READNEXT, a body that is not application/x-www-form-urlencoded, data with a pair lacking '=', an empty name or pair, ';', '+', a bad escape, an escaped name or a byte outside printable ASCII, a READNEXT after ENDFILE, a name and value both too long, two conditions at once. #4767: The task serves the one inbound HTTP request that whoever runs it STATES (http_request, as X37; unstated, each command is refused); WEB EXTRACT (server form) returns the stated scheme (CVDA HTTP 1096 / HTTPS 1029), host, HTTP method, HTTP version (the text the run states: ASSUMED), path, query string (none: length 0, area left alone: ASSUMED), the port and REQUESTTYPE HTTPYES, each length option read as the area's size and set to the piece's length, the areas written on NORMAL only; LENGERR RESP2 21 / 5 / 7 for a HOSTLENGTH / PATHLENGTH / VERSIONLEN not above zero; WEB RECEIVE INTO / LENGTH / MAXLENGTH / MEDIATYPE returns the stated body (cut at MAXLENGTH with LENGERR RESP2 57, LENGTH the bytes returned, LENGERR RESP2 16 for a MAXLENGTH not above zero, MEDIATYPE blank-padded to 56) with SRVCONVERT / NOSRVCONVERT changing nothing (program characters); WEB READ HTTPHEADER returns the value of the stated header of that exact name (INVREQ RESP2 43 no headers, NOTFND RESP2 1 no such header, LENGERR RESP2 1 VALUELENGTH not above zero); WEB WRITE HTTPHEADER adds a header to the response, recorded as WEB-HEADER and compared (a name written twice is two headers; LENGERR RESP2 35 / 55); refused: NOTRUNCATE, containers, every code-page option, SERVERCONV, BODYCHARSET, TYPE, the client forms (SESSTOKEN, REALM), HOSTTYPE, URIMAP, a LENGERR on a piece or value longer than its length, a METHODLENGTH / QUERYSTRLEN not above zero, a request with no body, a second RECEIVE, a header found only without case or stated twice, a header written after the response was sent, a name with a blank or colon, a length past its area, two conditions at once | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C, which answer one step list alike, now also for FORMFIELD / QUERYPARM and the browse forms; no cics-crucible case yet; ZECS001 still holds on pointer arithmetic and ADDRESS OF a subordinate item (X47), CALL ZUIDSTCK, GET COUNTER and its DOCTOKEN sends) |
| X39 | CICS | EXEC CICS LINK passes the caller's COMMAREA by address; EXEC CICS XCTL says only that the contents of the data area are passed. When a LINKed program XCTLs with (part of) its own DFHCOMMAREA, whether the target's writes reach the LINK caller is not documented, so a successful XCTL of the caller's area is refused by name in both runtimes, and in a model port (#4956) when the XCTL passes the DTO it was LINKed with or an object that DTO holds | REFUSED (IBM is silent) | no (unit-proven on CicsTask, the model-port DTO case included, and the det emission; a cobc regression refuses on the oracle's side) |
| X40 | CICS | EXEC CICS XCTL / LINK conditions INVREQ, LENGERR, NOTAUTH, PGMIDERR: with no RESP and no HANDLE CONDITION for the condition the task abends with the condition's abend code (AEIP, AEIV, AEY7, AEI0). NOTAUTH had no code in the shared table, so the det runtime threw 'no abend code known' and the stub printed '????'; LINK also takes a planned fault, as XCTL does. EIBRESP2 of a planned fault is the plan's RESP2 (#4986, X43) | ASSUMED | no (unit-proven on CicsTask and the stub's table; the CardDemo scenarios wait for their model ports) |
| X41 | CICS | WEB RETRIEVE DOCTOKEN(area) on the task that serves the stated request (http_request, as X37: unstated, refused) answers INVREQ RESP2 2 when no WEB SEND has been issued, NOTFND RESP2 1 when the last WEB SEND was not an ACTION(EVENTUAL) document send or was DOCDELETE, and NORMAL when the last WEB SEND was an EVENTUAL (or ACTION-omitted) document send that did not DOCDELETE: the 16-byte DOCTOKEN written is that of a new document of the task holding the document as it was sent (ASSUMED), the same token for every retrieve of that send; refused: a retrieve after a WEB SEND that ended in a condition, every option but DOCTOKEN (it is required), a literal DOCTOKEN, an unstated request | ASSUMED (REFUSED where IBM is silent) | no (unit-proven on CicsTask and the stub C, which answer one step list alike, NORMAL included; no cics-crucible case: its SPEC has no WEB event; no estate program issues it) |
| X42 | CICS | MOVE CONTAINER (rename across channels, TOCHANNEL made when absent, an existing AS overwritten) and STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER (the names of a channel's containers, in creation order, one token per browse) with IBM's RESP / RESP2: INVREQ 4, CHANNELERR 2, CONTAINERERR 10, END 2, TOKENERR 3; refused: a move onto itself or onto the other data type, a browse of a channel that changed, a browse with no channel, and the conditions no modelled state reaches (CHANNELERR 1 / 3, CONTAINERERR 18, INVREQ 30 / 31, ILLOGIC 1) | ASSUMED (REFUSED where IBM is silent) | cics-crucible ca-channel-browse (hand-traced, companion PR, not yet pinned; its browse, MOVE and TOKENERR / END steps; the cobol-stub side passes); unit-proven on CicsTask and the stub C, which answer one step list alike |
| X43 | CICS | EXEC CICS LINK documents ROLLEDBACK, SYSIDERR and TERMERR beyond XCTL's conditions. The region never raises them (no remote system, no unit of work to roll back, no terminal link) and resp.CONDITION_ABEND has no abend code for them that is sourced from IBM, so a scenario cannot plan them on a LINK (equivalence_cics.fault_lines refuses by name) and a program that depends on one stays unproven. EIBRESP2 / RESP2 after a failed XCTL or LINK is the RESP2 its event carries (a planned fault's PGMIDERR 3, NOTAUTH 101 ...), no longer derived from the condition's name | REFUSED | no (unit-proven on CicsTask and the harness's fault_lines) |
| X44 | CICS | DELETE CHANNEL (the channel and its containers go) and QUERY CHANNEL (CONTAINERCNT, the number of containers) with IBM's one condition, CHANNELERR RESP2 2; refused: deleting the program's current channel (IBM's RESP2 4 / 5 / 6 all fit it and it ranks none), a name that is blank or has an embedded blank, a channel an XCTL left behind; unreachable: CHANNELERR 3 (read-only). INQUIRE CONTAINER stays REFUSED by name (IBM documents it only for a BTS data-container; the channel browse is X42); a hand-traced cics-crucible case (ca-channel-browse, companion PR) covers X42 and X44 | ASSUMED (REFUSED where IBM is silent) | cics-crucible ca-channel-browse (hand-traced, companion PR, not yet pinned; cobol-stub passes both scenarios); unit-proven on CicsTask and the stub C, which answer one step list alike |
| X45 | CICS | A doubleword counter has the limits DEFINE DCOUNTER gave it (MINIMUM zero and MAXIMUM a doubleword of X'FF' when omitted; VALUE zero; INVREQ RESP2 407 for MAXIMUM below MINIMUM, 406 for VALUE below MINIMUM or above MAXIMUM + 1); GET DCOUNTER at MAXIMUM + 1 is SUPPRESSED RESP2 101 and leaves the counter, or with WRAP returns MINIMUM and goes on from it; QUERY DCOUNTER returns VALUE / MINIMUM / MAXIMUM; DELETE DCOUNTER; an INCREMENT beyond MAXIMUM - MINIMUM or past MAXIMUM + 1, a counter past a doubleword, and the limits of a counter DEFINE COUNTER made are refused | ASSUMED (REFUSED where IBM is silent) | no |
| X46 | CICS | FORMATTIME YYDDD / YYYYDDD / YYDDMM / YYYYDDMM (the date's parts in IBM's order, the day of the year three digits) and DAYCOUNT (1 January 1900 is day 1) / DAYOFMONTH / DAYOFWEEK (Sunday=0) / MONTHOFYEAR / YEAR / MILLISECONDS (binary integers, written by the receiving area's declared usage); DATE / DATEFORM / FULLDATE (the installation's DATFORM), DATESTRING / STRINGFORMAT / STRINGZONE (the zone) refused by name; DUMP TRANSACTION and the bare DUMP form refused by name (the outcome is the region's dump setup) | ASSUMED (REFUSED where IBM is silent) | no (the reference region's logs do not hold these forms; proved by the CicsTask unit test against Python's datetime and by the translated COBOL under GnuCOBOL, tests/cics_crucible/test_cics_runtimes.py and tests/cobol_mainframe/test_equivalence_cics.py) |
| X47 | CICS | A USAGE POINTER item holds the handle of a block of task storage; GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(byte) acquires one (every byte the INITIMG value; LENGERR RESP2 1 for FLENGTH below 1 or LENGTH zero, the pointer then zero), FREEMAIN DATAPOINTER(ptr) releases it (INVREQ RESP2 1 for an address GETMAIN did not return: a null pointer, a record's address), WEB RECEIVE SET(ptr) LENGTH(area) [MAXLENGTH] puts the request body in a new block (MAXLENGTH optional: all of it; LENGERR RESP2 16 leaves the pointer as it was, RESP2 57 cuts the body and sets it), SET ADDRESS OF record TO pointer / TO ADDRESS OF record makes a LINKAGE 01 record's bytes the block's (a real alias), SET pointer TO ADDRESS OF record gives the record's handle; refused: GETMAIN without INITIMG, a literal INITIMG, SHARED, NOSUSPEND, FREEMAIN DATA, a length above 256 MiB (LENGTH above 65520), a second FREEMAIN of the same block, FREEMAIN of a WEB RECEIVE SET body, SET ADDRESS OF a null / freed pointer, ADDRESS OF a WORKING-STORAGE record or a subordinate item, SET ADDRESS OF ... TO NULL, a pointer a REDEFINES overlays (pointer arithmetic) | ASSUMED (REFUSED where IBM is silent) | no (unit-proven: CicsTask and the stub C answer one list of steps alike, tests/cics_crucible/test_cics_runtimes.py _X47_CASES; DetCics's aliasing compiled and run, tests/cobol_mainframe/test_pointer_lane_4771.py; no estate program translates whole through it yet: ZECS001 also needs pointer arithmetic, ADDRESS OF a subordinate item, CALL ZUIDSTCK and the ZC##FILE templates) |
| X48 | CICS | The equivalence harness's `faults` take DUPKEY (RESP 15, RESP2 140) on READ / READNEXT / READPREV, where the read runs and delivers its record (INTO, and RIDFLD for a browse, and a READ UPDATE's hold) and answers DUPKEY; DUPREC (14, RESP2 150) on WRITE / REWRITE, where nothing is written; any other command / condition pair of the two, a wrong RESP2, and DUPKEY on DELETE are refused by name | ASSUMED (REFUSED where IBM is silent) | no (the reference region has no alternate index path to read through; proved on both sides by the stub (tests/equivalence/cics/ggcics.c) and CicsTask.withFaults against each other: tests/cobol_mainframe/test_equivalence_cics.py, tests/cics_crucible/test_cics_runtimes.py) |
| X49 | CICS | The equivalence harness's `faults` on a file command (READ, READNEXT, READPREV, STARTBR, ENDBR, WRITE, REWRITE, DELETE) take a condition only where IBM lists it for that command, and carry IBM's RESP2 (given, or the default when IBM gives one; INVREQ and LENGERR have several, so the scenario names one); an unlisted command / condition pair, a RESP2 IBM does not give, the data-table and RLS conditions (LOADING, RECORDBUSY, CHANGED, SUPPRESSED) and ILLOGIC on READNEXT / READPREV / REWRITE (IBM also ends the browse, not modelled) are refused by name | ASSUMED (REFUSED where IBM is silent) | no (an injection: the reference region's logs do not hold these conditions; the planned form is proved on both sides by the stub (tests/equivalence/cics/ggcics.c) and CicsTask.withFaults reading the same plan: tests/cics_crucible/test_file_fault_conditions.py, tests/cobol_mainframe/test_equivalence_cics.py) |
| X50 | CICS | A fullword counter has the limits DEFINE COUNTER gave it (MINIMUM zero and MAXIMUM X'7FFFFFFF' when omitted; VALUE zero; INVREQ RESP2 407 for MAXIMUM below MINIMUM or beyond X'7FFFFFFF', 406 for VALUE below MINIMUM or above MAXIMUM + 1); GET COUNTER at MAXIMUM + 1 is SUPPRESSED RESP2 101 and leaves the counter, or with WRAP returns MINIMUM and goes on from it; QUERY COUNTER returns VALUE / MINIMUM / MAXIMUM; an INCREMENT beyond MAXIMUM - MINIMUM or past MAXIMUM + 1, a VALUE or MINIMUM below zero, and the limits of a counter whose limits the run does not state are refused | ASSUMED (REFUSED where IBM is silent) | no |
| X51 | CICS | EXEC CICS RETURN TRANSID COMMAREA LENGTH and XCTL COMMAREA LENGTH hand the next task / the target LENGTH bytes (its EIBCALEN), every byte as it was; the det port passes the record's whole span beside its DTO (#4806, #4817), so CicsTask cuts those bytes at LENGTH (null: all; past the span: all of it), as the DTO's reading already is; a LINK's area is not cut (by address); a LENGTH past the DTO passes the COMMAREA as a byte[] (region EBCDIC), which a facade's handleTransaction answers as an Object by design | ASSUMED | no (unit-proven on CicsTask for RETURN, RETURN IMMEDIATE and XCTL, every LENGTH class: tests/cobol_mainframe/test_commarea_length_bytes_4817.py; no estate program differs by it: a conforming program never reads past EIBCALEN) |
| X52 | CICS | READ UPDATE TOKEN(d) returns a fullword token for the record held; REWRITE / DELETE / UNLOCK TOKEN(t) act on that record, and a token that matches none in use (never issued, spent, another file's) is INVREQ RESP2 47; a SYNCPOINT ends every token. The token's value is ASSUMED (the task's 1, 2, 3, ...). Refused: READNEXT / READPREV UPDATE [TOKEN] (RLS only), DELETE TOKEN with RIDFLD or GENERIC, REWRITE TOKEN whose FROM has another key | ASSUMED (REFUSED where IBM is silent) | unit-proven on CicsTask and the stub C over one scenario list (tests/cics_crucible/test_update_token_runtimes_5078.py: valid, invalid, reused, interleaved, wrong-file tokens; test_unlock_held_5079.py: UNLOCK without TOKEN); CBSA DELCUS (READ UPDATE TOKEN twice, DELETE TOKEN twice) translates whole (det_survey: 140 of 140 statements, compiles) |
| X53 | CICS | REWIND resets a counter that has reached its limit (MAXIMUM + 1) to its minimum, else SUPPRESSED RESP2 102, INVREQ 406 for an INCREMENT beyond (maximum - minimum) + 1; UPDATE sets the current value (INVREQ 406 below MINIMUM or above MAXIMUM + 1); GET REDUCE leaves a counter an INCREMENT would carry past MAXIMUM + 1 at MAXIMUM + 1, GET COMPAREMIN / COMPAREMAX hand the value out only when it is in range (either bound when COMPAREMAX is below COMPAREMIN), else SUPPRESSED RESP2 103 and the counter stays; NOSUSPEND is accepted and changes nothing (one task, no coupling-facility structure, so BUSY RESP2 500 cannot occur). Refused: UPDATE COMPAREMIN / COMPAREMAX, REWIND INCREMENT above 1, REDUCE with WRAP or at a counter already at its limit, COMPARE at a counter already at its limit, a negative VALUE / compare value of a fullword counter, REWIND / UPDATE of a counter whose limits the run does not state | ASSUMED (REFUSED where IBM is silent) | no |
| X54 | CICS | A DFHMDF field coded JUSTIFY=(RIGHT[,ZERO]) / (LEFT,ZERO) receives the operator's input right- or left-justified and filled with zeros or blanks, as BMS does; <f>L stays the length of the text typed. A field with no JUSTIFY is left-justified and blank padded, except a NUM field: RIGHT,ZERO (#5116) | ASSUMED (where IBM is silent) | unit-proven on DetJustify.place over the whole operand class (tests/cobol_mainframe/test_det_receive_map_justify_5082.py); PCCONF (pc-wizard) RECEIVE MAP into a JUSTIFY=(RIGHT,ZERO) field |
| X55 | CICS | A program written to CICS's macro-level API (DFHPC / DFHFC / DFHTC / DFHSC ... TYPE= macro calls, CSA / TCA addressing) or an assembler program written for CICS (DFHEIENT / DFHEISTG / EXEC CICS in HLASM) is its own refusal family: the scanner names it, the support matrix and blocker report count it per estate, and the det translator refuses it with the reason instead of reading it as COBOL with holes | REFUSED | no (no burned estate holds one; unit-proven on gitgalaxy/core/cics_macro_level.py and the det source check) |
| X56 | CICS | An OS/VS COBOL program's BLL cell list (the LINKAGE 01 of fullwords after DFHCOMMAREA, a FILLER first, one cell per 4096 bytes of each following 01) is rewritten before translation as IBM's 'Converting to VS COBOL II' says: the cells become POINTERs (X47), SET(cell) stays SET(pointer), SERVICE RELOAD record becomes SET ADDRESS OF record TO its cell, a long record's ADD 4096 secondary cells go, MOVE cell TO cell is SET; the det port and the GnuCOBOL oracle run that one program. IBM's chained storage areas are kept: a record whose cell changes with no SERVICE RELOAD later in its paragraph is addressed again through its cell at every paragraph name, and an address moved between a cell and a fullword of data is a token both runtimes number alike (ASSUMED). Every SET(cell) read command is its SET(pointer) form (X58). Refused whole by name (OS/VS COBOL BLL addressing: ...): a cell used as a number or moved to / from data that is no plain fullword, a reload or a paragraph name before a long record's secondary cells are reset, DECLARATIVES in a program whose records are addressed again at paragraph names, a secondary cell set any other way than ADD 4096, a cell as a command's data, SERVICE LABEL, SERVICE RELOAD of a non-LINKAGE item or of a record no cell addresses, DFHCOMMAREA after the list, a list in a COPY member | ASSUMED (REFUSED where IBM is silent) | yes, on a synthetic estate only (tests/cobol_mainframe/test_bll_cells_5119.py: a long record over two cells and a record aliased to it, a three-area chain walked through NEXTAREA and a paragraph name, and READQ TS SET(cell), each proven against GnuCOBOL end to end; every SET(cell) command and every refusal tested; the tokens' step lists answered alike by CicsTask and the stub, tests/cics_crucible/test_bll_tokens_5119.py). No corpus program uses BLL cells; estate-crucible's era strata (#5118 S4-S6) are to carry the corpus cases |
| X57 | CICS | READQ TD QUEUE INTO [LENGTH]: a destructive, first-in first-out read of the queue the task's own WRITEQ TDs fill; QZERO for an empty queue, QIDERR for a queue the CSD does not define, LENGERR (the record read and lost, INTO holding its first LENGTH bytes) for a record longer than LENGTH or a LENGTH of zero, LENGERR with nothing read for a negative LENGTH, LENGTH set to the record's own length. DELETEQ TD: every record of an intrapartition queue; QIDERR; INVREQ for an extrapartition queue. (Since #5168, X61 models extrapartition queues, SET, NOSUSPEND, INDIRECT and LOGICAL recovery.) Refused by name in X57: READQ TD of an extrapartition queue (and of any queue whose CSD TYPE is neither INTRA nor EXTRA), READQ TD SET / SYSID / NOSUSPEND, DELETEQ TD SYSID and of a queue with a TYPE other than INTRA / EXTRA, a record moved past INTO. The WRITEQ TD event keeps its shape | ASSUMED (REFUSED where IBM is silent) | no corpus program issues either command yet; proven on both runtimes with hand-traced operation lists (tests/cics_crucible/test_td_queue_5079.py) and the translator's refusals (tests/cobol_mainframe/test_equivalence_cics.py) |
| X58 | CICS | Each command, given SET(pointer-item) where it used to take INTO, puts a copy of the data in a new block of task storage and the block's handle in the pointer (the pointer lane of X47); SET ADDRESS OF a LINKAGE 01 record then reads it. LENGTH / FLENGTH is the data's length. The pointer ends where IBM says: RECEIVE and READQ TS at the next command of the kind, GET CONTAINER at the next GET CONTAINER SET of the same container or its DELETE / MOVE / the channel's DELETE, READ at the next READ of the file or a REWRITE / DELETE / UNLOCK (a READ UPDATE SET also at SYNCPOINT), READNEXT / READPREV at the next SET of the browse, its ENDBR or a SYNCPOINT; RETRIEVE states no end (to the task's end, ASSUMED). An ended pointer's storage reads as zeros (ASSUMED). A condition that delivers no data leaves the pointer as it was (ASSUMED). Refused by name: SET with INTO, a missing or literal LENGTH where IBM requires a data area, RBA / RRN / XRBA, a LENGTH on a browse SET, BYTEOFFSET, FREEMAIN of any of these blocks, a PUT or MOVE CONTAINER onto a container whose GET CONTAINER SET pointer is held; SEND MAP / RECEIVE MAP / SEND CONTROL SET (BMS storage) and LOAD SET, GETMAIN64 / FREEMAIN64 stay refused | ASSUMED (REFUSED where IBM is silent) | no (unit-proven: the stub and CicsTask answer one list of 37 step lists alike, tests/cics_crucible/test_cics_set_pointer_5042.py; the translators' shapes and refusals and a compiled DetCics run, tests/cobol_mainframe/test_pointer_lane_5042.py; no estate program translates whole through one of these yet) |
| X59 | CICS | EXEC CICS ADDRESS EIB(ptr) and COMMAREA(ptr) set a pointer to the task's own EIB / DFHCOMMAREA record (the pointer lane of X47): a LINKAGE record set to the pointer shares the bytes, so the EIB's later updates and a write through the COMMAREA view show in both. The command has no condition (NORMAL). A task with no COMMAREA (EIBCALEN 0) is refused when it runs: IBM sets the pointer to X'FF000000', which is not the COBOL NULL a pointer handle can hold. Refused by name: ADDRESS CWA, TWA, TCTUA and ACEE (system areas the region does not define), the old ADDRESS SET form, ADDRESS COMMAREA in a program with no 01 DFHCOMMAREA, and the old-style sweep: SEND PAGE and PURGE MESSAGE (a BMS logical message), CONVERSE on a terminal, POST and WAIT EVENT (timer-event control areas, one task runs at a time) | ASSUMED (REFUSED where IBM is silent) | no corpus program issues them yet; proven end to end on GnuCOBOL with the stub and on the det port with a hand-traced program (tests/cobol_mainframe/test_address_e2e_5079.py), the translators' shapes and refusals and both runtimes' no-COMMAREA refusal (tests/cobol_mainframe/test_address_5079.py) |
| X60 | CICS | A scenario can plan ENQBUSY (RESP 55) for an ENQ by the RESOURCE operand as the program writes it; RESP2 is 0 because IBM states none for ENQBUSY. The ENQ must say NOSUSPEND: without it IBM suspends the task and the runtimes refuse. ENQ's other conditions (INVREQ RESP2 2, LENGERR RESP2 1) come from the program's own operands, never from a plan. Refused: ENQBUSY planned for any other command, any other condition planned for ENQ, a RESP2 on an ENQBUSY plan, a planned-busy ENQ without NOSUSPEND, a resource that is no data-name of 1 to 16 characters | ASSUMED (REFUSED where IBM is silent) | no |
| X61 | CICS | READQ TD SET(ptr) LENGTH(data-area) puts the record in a new block valid to the next READQ TD (X58's pointer lane), LENGTH the record's length; NOSUSPEND is accepted and changes nothing (QBUSY needs a second task writing a logically recoverable queue). An extrapartition queue (TYPE EXTRA) answers by its definition: OPENTIME(DEFERRED) is closed, so NOTOPEN (19); TYPEFILE(OUTPUT) open, INVREQ (16); TYPEFILE(INPUT) open reads its records first in first out, QZERO at the end. A case seeds (text the data encoding holds whole, non-ASCII included) the records of an intrapartition queue or an input data set ("td"). WRITEQ TD to an extrapartition queue: INVREQ (16) when it is open for input, NOTOPEN (19) when closed (#5168 round 2). RECOVSTATUS(LOGICAL): SYNCPOINT ROLLBACK, or a task's abend, puts the queue back as it was at the last SYNCPOINT (reads, writes and DELETEQ alike); NO commits at once. An INDIRECT queue routes READQ / WRITEQ / DELETEQ to its INDIRECTNAME, itself possibly indirect. Refused by name: SYSID and REMOTE queues, IOERR (no data set), RDBACK or no TYPEFILE, RECOVSTATUS(PHYSICAL) with a SYNCPOINT ROLLBACK, a WRITEQ TD that brings a queue with a TRANSID to its TRIGGERLEVEL (automatic task initiation), an INDIRECT queue with no INDIRECTNAME / an undefined target / a loop, a SYNCPOINT ROLLBACK after a SYNCPOINT (CicsTask) | ASSUMED (REFUSED where IBM is silent) | no corpus program issues these forms yet; proven on both runtimes with hand-traced operation lists (tests/cics_crucible/test_td_queue_5168.py, 17 scenarios), the translators' shapes and refusals (tests/cobol_mainframe/test_equivalence_cics.py, test_det_translate.py) and end to end against GnuCOBOL (tests/cobol_mainframe/test_td_queue_e2e_5168.py) |
| X62 | CICS | The resource map is built from definition sources in the repository (CSD decks, assembled macro tables, including tables in JCL assembler SYSIN). What a running region installed, enabled or changed through CEDA, CEMT or EXEC CICS SET / CSD commands is not in a source tree, so no scan can state it; the map names that limit instead of guessing | REFUSED | no (a static property: nothing to reach) |
| L1 | LE | CEEDAYS: numeric date pictures (YYYY MM DD in any order, YYYY DDD) read as their span; date characters past the span ignored (documented), an all-blank picture tail ignored (assumed), a non-blank tail refused; open conditions refused by name | MATCHED / ASSUMED / REFUSED | yes (CardDemo carddemo-dateutil; CBSA cbsa-crecust is refused by name, #4952) |
| L2 | LE | CEE3ABD abend codes | MATCHED | yes |
| L3 | LE | WORKING-STORAGE with no VALUE clause: GnuCOBOL's spaces vs LE's STORAGE option on z/OS | ASSUMED | yes (CardDemo READACCT OUTFILE, 2 bytes; CBSA CRDTAGY1-5 container-short, WS-CONT-IN past a short container) |
| L4 | LE | CEEIGZCT: a stand-in declaring the symbolic feedback code CEE000 only (CBSA CRECUST, #4884) | ASSUMED | yes (cbsa-crecust, #4952) |
| L5 | LE | CEELOCT: Lilian day, seconds and YYYYMMDDHHMISS999 from the pinned clock, feedback all zero; the unwritten tail of IBM's longer Gregorian field and the float's representation assumed | ASSUMED | yes (CBSA CRECUST, cbsa-crecust, #4952) |
| L6 | LE | LE date/time services: Lilian date / seconds semantics and the documented feedback codes; GMT is the pinned clock; the VSTRING output layout assumed; open conditions refused by name | MATCHED / ASSUMED / REFUSED | no (CBSA BANKDATA, the caller of CEEGMT and CEEDATM, has no equivalence case: its CUSTOMER-FILE and its Db2 estate are not a case yet) |
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
instrument). The rows below are rendered by one table in code (`compiler_options.OPTION_TABLE`; `estate_options.EffectiveOptions.unhonoured`): the estate's PARM, installation defaults and CBL cards are resolved against it, so an option the harness cannot honour is no longer merely recorded. Citations: Enterprise COBOL for z/OS 6.x Programming Guide, "Compiler options", the option's own section; the defaults are those the 6.4 page lists (FLOAT's default is not on it: HEX is what register C6 models).

| option | (1) changes results? | (2) cobc | (3) det port | (4) otherwise | register |
|---|---|---|---|---|---|
| `TRUNC(STD)` (IBM default) | yes: a binary receiver keeps its PICTURE's digits | `-fbinary-truncate` | `Cobol.swapTruncBinary(true)` | -- | C1 |
| `TRUNC(BIN)` | yes: a binary receiver keeps its bytes | `-fnotrunc` | `Cobol.swapTruncBinary(false)` | -- | C1 |
| `TRUNC(OPT)` | only for a binary value past its PICTURE, where IBM's result is unpredictable; conforming values compute as STD | `-fbinary-truncate` (STD: equal for conforming values) | STD, plus `Cobol.swapTruncOpt(true)`: a value past a COMP / COMP-4 / BINARY receiver's PICTURE stops by name ("TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable") | a port without the stop (model, generated) is proven as STD: a declared difference (`option_differences`) | C1, C5 |
| `ARITH(COMPAT)` / `ARITH(EXTEND)` | yes: EXTEND widens intermediates to 31 digits | none for EXTEND | none | `ARITH(EXTEND)` refused by name (`COBC_OPTIONS`) | C5 |
| `INTDATE(ANSI)` / `INTDATE(LILIAN)` | yes: day 1 of INTEGER-OF-DATE moves from 1601-01-01 to 1582-10-15 | none for LILIAN | none | `INTDATE(LILIAN)` refused by name (`COBC_OPTIONS`) | C5 |
| `NUMPROC(NOPFD\|PFD\|MIG)` | only for a sign that is not preferred | none needed | PFD refuses a non-preferred sign (`Codec.numprocPfd`) | MIG compiles as NOPFD from Enterprise COBOL 5 (`numproc_mig`) | C5 |
| `ZONEDATA(PFD)` (IBM default) | no for valid zone bits (an invalid one is refused by C11) | none needed | refuses a non-digit zoned operand | -- | C11 |
| `ZONEDATA(NOPFD\|MIG)` | yes: defines what invalid zone bits / digits do in MOVE, compare and arithmetic (APAR PI57769) | none | none | refused by name | C5 |
| `INVDATA` (default `NOINVDATA`) | yes: supersedes ZONEDATA, defines what invalid DISPLAY / PACKED-DECIMAL data does | none | none | any `INVDATA` refused by name (its sub-option semantics are not read here; owner decision if ever needed) | C5 |
| `CODEPAGE(ccsid)` (default 1140) | yes: compile-time and runtime character conversion (literals, collating, national) | none: the oracle runs the data in the case's `data_encoding` | the same data code page | honoured for 1140 / 37 (the IBM default, as every proof assumes) or the CCSID of the case's `data_encoding`; any other (GenApp's `CODEPAGE(285)`) is a declared difference | C5 |
| `NSYMBOL(NATIONAL)` (IBM default) | only for PIC N | none needed | national text refused (#4272) | -- | C5 |
| `NSYMBOL(DBCS)` | yes: N literals / PIC N are DBCS | none | none | refused by name | C5 |
| `DISPSIGN(COMPAT)` (IBM default) | no | none needed | -- | -- | C5 |
| `DISPSIGN(SEP)` | yes: DISPLAY of a signed numeric item | none | none | refused by name | C5 |
| `FLOAT(HEX)` / `S390` | the det port models hexadecimal floating point | none needed | HFP (`Hfp`) | -- | C6 |
| `FLOAT(NATIVE)` | yes: IEEE binary floating point | none | none | refused by name | C6 |
| `AFP(VOLATILE\|NOVOLATILE)` | no: which floating-point registers the code uses | none needed | -- | recorded only | C5 |
| `NOSSRANGE` (IBM default) / `SSRANGE` | only on an out-of-range subscript or reference modification: undefined under NOSSRANGE, an abend under SSRANGE | none (no check) | no check | `SSRANGE` is proven as NOSSRANGE: a declared difference, so a run with no violation is IBM's | C5 |
| `NONUMCHECK` (IBM default) / `NUMCHECK` | only on invalid numeric data in a sending item (message or abend under NUMCHECK) | none | none | `NUMCHECK` is proven as NONUMCHECK: a declared difference | C5 |
| `NOINITCHECK` (IBM default) / `INITCHECK` | no: compile-time warnings for uninitialised items | none needed | -- | recorded only | C5 |
| `OPTIMIZE(0\|1\|2\|STD\|FULL)` | no for defined behaviour: run time and storage | none needed | -- | recorded only (CBSA's `OPT` = `OPTIMIZE(1)`) | C5 |

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
  | MOVE zoned to zoned of ONE shape (digits, scale, sign, sign position, size equal: COCRDUPC's `MOVE CARD-CVV-CD-N TO CARD-UPDATE-CVV-CD`, both PIC 9(3)) | none: cobc compiles it as a memcpy (`cb_build_move_copy`), libcob never runs. IBM agrees (below): the bytes are copied as they are | the bytes copied as they are, a space, letter or sign byte too, no sign rewrite; measured per sender shape (the `OWN` receiver of `test_det_nondigit_zoned.py`) |
  | MOVE to numeric-edited (`MOVE A6 TO E7`: 7 spaces) | `cob_move_display_to_edited` | the digit bytes fed to the picture as they are; only a '0' is suppressed, so a space stays a space and `Z(6)9` of spaces is 7 spaces; X'00' stays X'00' |
  | MOVE to packed (COMP-3) | `cob_move_display_to_packed` | a nibble pair is `(hi * 16 + lo) mod 256` of the digits' values (byte - '0'; a space 0), so `12A4` is `01 31 4C`; reading such a packed item back as a number is still the runtime's (nibble above 9 reads as 9; the oracle prints garbage) -- the tests compare it as the COMP-5 number its bytes are |
  | COMPUTE / ADD / SUBTRACT operand (`COMPUTE B9 = A6` 709551600) | `cob_decimal_set_display` | a first byte X'FF' is +10^size and X'00' -10^size; else leading bytes whose low nibble is 0 (zeros, spaces, low-values) are skipped and the rest accumulate as `value * 10 + (byte - '0')` in an unsigned 64-bit integer that wraps (a space -16, `A` 17), the sign applied after. 19 or more digits left after the skipping: refused by name |
  | `ADD x TO y` / `SUBTRACT x FROM y`, x a zoned field of at most 9 digits, y not COMP under TRUNC(STD), no ROUNDED / SIZE ERROR | `cob_add_int (y, cob_get_int (x))` (cobc's `cb_build_optim_add`) | x read as an int: every digit position counts (a space -16), nothing skipped, nothing wrapped at 64 bits. `gen.py` marks these statements (`Cobol.intOperand`), the runtime decides on TRUNC |
  | `IF x = 0`, `IF x > 5`, `IF x < y`, `IS POSITIVE` (`IF A6 = 0` false) | `cob_cmp_numdisp` for an unsigned or trailing-sign item without decimals; `cob_numeric_cmp` through the decimal for a leading or separate sign or decimal places | numdisp: every digit position in a signed 64-bit integer, nothing skipped, a sign byte that is no overpunch (a space too) 0, nothing written back; the decimal: as an arithmetic operand. NUMERIC is unchanged (a space is not numeric). 19 or more digits: refused by name |
  | MOVE to binary | `cob_move_display_to_binary` (#4652) | unchanged, but a sign byte that is no sign (`!`, X'FF') is no longer refused: it reads as above; a SEPARATE sign other than + - space is still refused |

  IBM has no result for any of these (a zoned item with a digit nibble above 9 or a zone that is no sign is not NUMERIC;
  its use in arithmetic or a MOVE is undefined), and on z/OS a space is X'40', whose digit nibble 0 most likely reads as
  0: the proofs say the port computes what GnuCOBOL computes for these bytes, not what z/OS would. Not modelled, so
  still different or untested: a zoned item with a P position (refused by name, below), DISPLAY of a byte above X'7F' (the port writes UTF-8, the oracle the
  byte), a hex literal naming a line-end character in a MOVE (`X'0A'`, `X'0D'`: the generated Java string breaks).
- **Same-shape zoned MOVE: what IBM does (#4875).** IBM documents no result for non-digit data in a numeric item, but its
  APAR PH21007 ("COBOL V6.2 was inadvertently generating code to fix up bad signnibbles in zoned to zoned moves",
  <https://www.ibm.com/support/pages/apar/PH21007>, against Enterprise COBOL 6.3) says that under `ZONEDATA(NOPFD|MIG)` --
  the options that replace the pre-V5 `NUMPROC(NOPFD|MIG)`, and CardDemo's default, its programs carry no option -- the
  compiler set the receiver's sign nibble after a zoned-to-zoned MOVE whose receiver's sign or length differs from the
  sender's, and was changed "to match the pre-V5 behavior": the invalid sign nibble is kept. A MOVE between items of one
  shape is not one of those, so IBM copies the bytes as they are, as cobc does: a trailing space (X'40' on z/OS) stays,
  and the CVV is `   `. MATCHED for the same-shape case; the differing-shape moves stay the oracle's rules above. Read
  from the APAR text, not run on z/OS (#4050).
- **A non-digit in the RECEIVER of ADD / SUBTRACT / MULTIPLY / DIVIDE (#4692) -- REFUSED by name.** `ADD 1 TO CTR` with
  CTR PIC 9(4) holding spaces reads CTR before it stores. Measured against cobc 3.1.2 (`-std=ibm -fsign=EBCDIC`, TRUNC(STD)
  and TRUNC(BIN), also -O2), per receiver shape (unsigned, SIGN TRAILING / LEADING, TRAILING / LEADING SEPARATE) holding
  spaces, letters, low-values, X'FF', `!`, a bad sign byte, over ADD / SUBTRACT of a literal, a field, ROUNDED, ON SIZE
  ERROR, MULTIPLY, DIVIDE: `cob_add_int` does NOT add on the bytes in place here (the issue's `cob_display_add_int`); it
  reads the receiver through `cob_decimal_set_display`, as it does an operand (`ADD 1 TO` four spaces is 1601, `12A4` is
  1375), so the det runtime's old read agreed with cobc byte for byte. IBM is the reference and says nothing about the
  digits: ZONEDATA(PFD), the default (and the option the estate's evidence records carry), "assumes the zone bits are
  valid"; under ZONEDATA(NOPFD|MIG) an ADD corrects invalid zone bits (APAR PI57769, Enterprise COBOL 5.1: "The compiler
  was fixed to not eliminate the addition of a USAGE DISPLAY data item and 0"), and ZONEDATA(NOPFD|MIG) widened to MOVEs,
  comparisons and computations in APAR PI90571; neither says what a non-digit digit position adds up to (on z/OS a space
  is X'40', a letter's digit nibble is not its byte minus '0'). So the port refuses (`Cobol.receiverNum`: "arithmetic
  whose receiver is a zoned item holding a non-digit is not modelled", at run time, before the statement stores) rather
  than prove cobc's guess. A receiver that is only overwritten (MOVE, GIVING) or read as an operand (`COMPUTE y = y + 1`,
  the operand rule above) is unchanged and measured (`test_det_nondigit_zoned.py`, `nondigit_zoned_receiver_expected.txt`).
  Reach (static scan, 2026-10-11, heuristic upper bound): of 88 ADD / SUBTRACT / MULTIPLY / DIVIDE statements with a
  zoned receiver in the six burned estates, 17 in CardDemo (8 programs; page / screen counters of a commarea cleared by
  `MOVE SPACES`, CBEXPORT's sequence counter, COTRN02C's `MOVE TRAN-ID TO WS-TRAN-ID-N` after `MOVE HIGH-VALUES TO
  TRAN-ID`) can see a non-digit; CBSA 4, GenApp 23, the others 0 cannot. Per verb (#4692): ADD / SUBTRACT / MULTIPLY / DIVIDE
  refuse a dirty receiver (above); MOVE and GIVING overwrite it, so the receiver is not read (modelled, measured);
  COMPUTE reads it as an operand (modelled).
- **A zoned item with a P position holding a non-digit, as a sender (#4685, #4692) -- REFUSED by name.** Measured against
  cobc 3.1.2 (`-std=ibm -fsign=EBCDIC`, TRUNC STD and BIN): a left-P item (`PIC VPP99`) MOVEd to a binary item makes
  the program hang (the 14-operation probe never finished; `timeout` killed it), and a right-P one (`PIC 99PP`) is
  computed by no explainable rule (`ADD S TO DS` of two spaces gives 17595-, not the -1595 its bytes' `-16 * 100 + 5`
  would be). IBM documents no result for non-digit data. So the port refuses, at run time, a MOVE, an ADD / SUBTRACT /
  COMPUTE operand or a comparison that reads such an item (`Zoned.refuseP`, `Cobol.nonDigitToBinary`,
  `Cobol.moveNonDigit`: "... a zoned item with a P scaling position ... is not modelled"); a digit-only P item is read
  as ever (PSCALE, `test_det_programs.py`). Tested over `99PP`, `S99PP`, `VPP99`, `SVPP99` x MOVE to zoned / packed /
  binary / edited, ADD, SUBTRACT, COMPUTE, comparison (`test_det_nondigit_zoned.py`).
  The rest of the sender class (#4996), against the Enterprise COBOL for z/OS 6.4 Language Reference (every quote below
  is from `lrmvs.pdf`; where IBM rejects, the port refuses by name rather than model cobc):
  - **STRING -- REFUSED (translation hole).** STRING rules: "If identifier-1 or identifier-2 references a data item of
    category numeric, each numeric item must be described as an integer without the symbol 'P' in its PICTURE
    character-string." A P-scaled (or noninteger) numeric sender, or DELIMITED BY item, is a compile error on z/OS; cobc
    sends its stored bytes. A reference-modified one is alphanumeric (below) and is translated.
  - **MOVE of a noninteger numeric (`VPP99`, `SVPP99`, `9V99`) to an alphabetic / alphanumeric / alphanumeric-edited
    item -- REFUSED (translation hole).** "Valid and invalid elementary moves" (Table 51), row "Numeric noninteger
    sending item", columns alphabetic / alphanumeric / alphanumeric-edited: NO. cobc warns ("MOVE of non-integer to
    alphanumeric") and moves. A right-P item (`99PP`, `S99PP`) is an integer: the MOVE is valid and "any digit positions
    described with picture symbol P in the sending item are considered to have the value zero. Each P is counted in
    the size of the sending item" (MOVE, usage note 1), which is what the port and cobc do (`1200  ` for `12`). A
    non-digit in its digit positions is C11's undefined data, copied as for an unscaled item (ASSUMED).
  - **Reference modification -- MODELLED.** A numeric DISPLAY data-name-1 "is operated upon for purposes of reference
    modification as if it were redefined as a data item of category alphanumeric with the same size"; the rules name no
    P restriction, and in operations other than the numeric ones listed under "P symbol" the Ps "are ignored and are not
    counted in the size of the operand", so `S(1:1)` of `99PP` is its first stored byte (cobc agrees).
  - **DISPLAY of a P-scaled item -- REFUSED (translation hole, #4670).** The DISPLAY page names no P rule and says only
    "No other categories of data require conversion" beyond binary / packed / float / pointer; DISPLAY is none of the
    operations "P symbol" lists as using the algebraic value, so IBM writes the item's stored bytes (an inference from
    those two statements, not a sentence about DISPLAY). cobc writes the P positions as digits (`[0012]` for `99PP`
    holding `12`), so the port refuses rather than print either.
  - Also refused already, now tested: MULTIPLY / DIVIDE operands (`Zoned.operand`), a P item as the receiver of ADD /
    SUBTRACT / MULTIPLY / DIVIDE (#4889), `INITIALIZE ... REPLACING` with such a sender (hole).
  A digit-only P item's value is cobc's on every arithmetic / compare / MOVE read, and a P item's reference-modified
  and right-P MOVE-to-alphanumeric bytes are cobc's (`nondigit_zoned_p_expected.txt`, 260 cobc-measured cases; a left-P
  MOVE to binary is left out, cobc hangs on it even digit-only).
- **The rest of the non-integer / non-digit sender class (#5032)**, against the Enterprise COBOL for z/OS 6.4 Language
  Reference. Where IBM rejects or documents no result, the port refuses by name rather than model cobc:
  - **MOVE of a noninteger numeric item to a NATIONAL or national-edited item -- REFUSED (already, at the source).**
    Table 51 marks it invalid, and the translator refuses every national item (PIC N / G, USAGE NATIONAL / DISPLAY-1,
    an N / G / U literal) before generation (#4462, #4664), so no sender shape, noninteger or not, reaches a national
    receiver. Tested over `9V99`, `S9V99`, `VPP99`, `SVPP99`, `99PP`, `9(3)` x six national declarations
    (`test_det_nondigit_zoned.py`).
  - **UNSTRING -- REFUSED (translation hole), two different grounds (`Gen.unstring_operands`).** IBM's rules
    (Language Reference, UNSTRING): a numeric `INTO` item may not have the symbol 'P', and a `COUNT IN` / `POINTER` /
    `TALLYING IN` item must be an integer without a P; the port refuses a violation as IBM does. It does NOT require an
    integer `INTO` item. The port's own CONSERVATIVE choice (REFUSED by name, ASSUMED, not an IBM compile error; the
    Language Reference was not available to check it): a numeric sending item or `DELIMITED BY` / `DELIMITER IN`
    item, and a decimal (no P) numeric `INTO` item, are not modelled -- GnuCOBOL moves their stored bytes and the port
    does not translate either. An integer numeric `INTO` item and a reference-modified operand (alphanumeric) are
    translated as before.
  - **A signed zoned sender whose sign byte is no sign (`!` X'21', X'FF'), MOVEd to an alphanumeric or
    alphanumeric-edited item -- REFUSED at run time.** IBM treats the sender as an unsigned integer and documents no
    result for an invalid sign (undefined data, as above); cobc turns the byte into a digit (`GET_SIGN` /
    `PUT_SIGN`), the port used to copy it. `Cobol.refuseUndefinedSign` refuses a sign byte that is not a digit, an
    overpunch (`{` `A`-`I` `}` `J`-`R`) or a space, and a separate sign that is not `+` `-` or a space, the same
    set the MOVE-to-binary refusal uses (`nonDigitSign`). Every other sign byte moves as ever.

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
- **Duplicates of an alternate key (#4876) -- the first duplicate is IBM's.** GnuCOBOL's BDB returns a non-unique
  alternate key's duplicates in the order they were written, and orders its primary key by bytes whatever the PROGRAM
  COLLATING SEQUENCE (measured on cobc 3.1.2: no flag or clause changes it; there is no `-fdefault-colseq`). VSAM returns
  the pointers of a non-unique alternate key in prime-key order, EBCDIC's, and the det runtime (`DetFiles.Indexed`,
  `DetCics.Store`) does the same. So the harness writes a generated indexed input in cp037 order of its primary key
  (`equivalence_inputs.ibm_key_order`): the oracle loads it in that order and its first duplicate is IBM's too. Found by
  carddemo-intcalc-generated (CBACT04C reads XREFFILE by account; the generated card numbers mix letters and digits), now
  proven. Not settled on z/OS (#4050): that IBM's pointer order for a base cluster loaded by the program is prime-key
  order. Still different: a browse (READ NEXT / START) of a primary key mixing letters and digits, which the oracle
  answers in ASCII; no case browses such a key.
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

### F5. RECORD KEY / ALTERNATE RECORD KEY outside the file's record
- IBM Enterprise COBOL Language Reference, RECORD KEY clause (ALTERNATE RECORD KEY likewise): the key data item is
  defined in a record description entry of the file the SELECT names. A key defined elsewhere (a WORKING-STORAGE
  item such as a `COPY`'d work record) is not a valid program.
- The instrument agrees: GnuCOBOL 3, `-std=ibm`, stops with `'EXPORT-SEQUENCE-NUM' is not defined` (measured
  2026-10-09 on CardDemo CBEXPORT; the key is in WORKING-STORAGE, the FD record is one `PIC X(500)`). So no
  equivalence case can build the COBOL side.
- The det translator reads each SELECT's RECORD KEY and every ALTERNATE RECORD KEY, resolves it, and refuses the file
  by name (`<key> is not defined in a record of file <select>`) when its 01 record is not one of the FD's records
  (any of several 01 records under the FD counts; a key reached through `COPY` inside the FD counts). A statement
  that uses the file is refused with that reason, so the program does not count as translated whole.
  Never translated: the port does not guess which bytes of the record the author meant.
- RELATIVE KEY has the opposite placement rule in IBM's reference (not in the file's own record); `ORGANIZATION
  IS RELATIVE` is refused by name as a whole, so that rule is not reached.

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
  (IBM, LINK conditions; `CicsTask.transferResp2`, the event's RESP2, #4986); the others IBM lists (PGMIDERR 2 / 3, NOTAUTH 101, INVREQ ...) the
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
  CHANNEL (the next task's channel: neither harness carries it, and no corpus program uses it); LINK / XCTL with both CHANNEL and COMMAREA. At run
  time: a PUT naming the other data type for an existing container (IBM says DATATYPE "applies only to new
  containers" and also lists INVREQ RESP2 33 for "an attempt ... to change the data-type"); a channel an XCTL left
  behind (IBM's scope tables do not say); an FLENGTH past FROM / INTO, or a negative one on GET; a name that is
  blank, longer than 16, or holds a character outside IBM's set on a command whose page says nothing of one (GET /
  DELETE CONTAINER, LINK / XCTL CHANNEL, the browse and MOVE commands); a name holding & < or the not sign (RUN
  TRANSID's page allows them in a channel name, PUT CONTAINER's does not); on PUT CONTAINER, two illegal names, or an
  illegal one with a negative FLENGTH or no channel in scope (which condition IBM raises first is not documented).
- **Names (#4950).** PUT CONTAINER (CHANNEL) documents the set: "A-Z a-z 0-9 $ @ # / % ? ! : | " = , ; > . - and _.
  Leading and embedded blank characters are not permitted", with CHANNELERR RESP2 1 for an illegal CHANNEL name and
  CONTAINERERR RESP2 18 for an illegal CONTAINER name. Both runtimes model exactly that (before, any name with no blank
  was accepted, `^` or `~` included). The other commands' pages give no set and no condition.
- **Reached.** cics-crucible ca-channel-containers (2 scenarios: CHAR / BIT / APPEND, LINK and XCTL CHANNEL, the
  current channel, truncation and LENGERR, NODATA, CONTAINERERR / CHANNELERR / INVREQ by RESP and by HANDLE
  CONDITION, AEZJ by default), cobol-stub and the det port both passing the hand-written logs (crucible branch
  `cases/channel-containers`, not yet released or pinned).

### X18. Interval control and the async API: START / RETRIEVE / CANCEL / RUN TRANSID / FETCH / FREE CHILD — ASSUMED, REFUSED where IBM is silent (#4270 slice 2, #4950)
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
  **#4950: the child schedule (ASSUMED, IBM is silent on the order).** A RUN child is dispatched at its parent's next
  wait -- a DELAY, or a FETCH without NOSUSPEND (it waits, or has a TIMEOUT) -- in RUN order, and runs to its end
  before its parent resumes (one quasi-reentrant TCB: a task keeps control until it waits). A task takes no processor
  time (X4): a child completes at its dispatch time plus its own DELAYs, on a scheduling clock that counts only DELAYs
  and FETCH waits (EIBTIME / ASKTIME stay at dispatch: a child's EIBDATE / EIBTIME are its parent's). A child never
  dispatched (its parent ends first) is not run. A child is a non-terminal task: no COMMAREA, EIBAID X'00', EIBTASKN
  its parent's plus its RUN number (a stated fact on both sides, X21), its current channel the copy RUN made. FETCH at
  the parent's scheduling time T: NOSUSPEND finds a child that completed before T, else NOTFINISHED 52 (IBM: "NOSUSPEND
  was specified, but there were no completed children to fetch"); a waiting FETCH resumes when the child completes;
  TIMEOUT(t) is NOTFINISHED 53 when none completes before T + t ("No children have completed within the interval");
  FETCH ANY takes the first to complete, RUN order on a tie; NOTFND RESP2 1 when no unfetched child is left, INVREQ 52
  with no children, INVREQ 50 for a token that is not a child's or was freed (FREE CHILD). On NORMAL: ANY gets the
  token, COMPSTATUS the CVDA NORMAL (1016) or ABEND (900), ABCODE the abend code of a child that abended (left alone
  otherwise), CHANNEL the name of a copy of the channel the child left -- a name of the harness's own,
  GGREPLY000000001... (IBM generates it; its bytes are not documented). RUN / START CHANNEL take IBM's character set
  ("The acceptable characters are A-Z a-z 0-9 $ @ # . / - _ % & ? ! : | " = ¬ , ; < >. Leading and embedded
  blank characters are not permitted"): any other is CHANNELERR RESP2 1. START CHANNEL hands the started task a copy
  of the containers as they are at the START (the event carries it). Both sides: `ggcics.c` (a child is the task
  re-run as a process of its own -- GGCCHLD names its program, `childprogs.cfg` the case's `child_programs` -- its
  end state in end.txt / reply.cfg) and CicsTask (`dispatchChildren`, `delay`, `fetch`, `freeChild`); a child's events
  are one CHILD event, compared as a task's (`equivalence_cics.compare_events`).
  **#5089: nested RUN TRANSID (ASSUMED where IBM is silent).** IBM's RUN TRANSID page puts no restriction on who may
  issue it ("The started task (child task) runs asynchronously with the starting task (parent task)"; "The parent task
  will get a response back when the API command FETCH CHILD or FETCH ANY is issued"), and IBM's Redbook (SG24-8411)
  describes a parent that may "initiate further child tasks"; its FETCH CHILD page says only that the token "will have
  been returned from the RUN TRANSID command", INVREQ RESP2 50 for data that "is not a valid child token". The model: a
  RUN child is a task like its parent (the same rules, at every level, each task with its own children, tokens and
  scheduling clock). A child's RUN / FETCH / FREE CHILD concern only the tasks it started: its FETCH ANY with none is
  INVREQ 52, a token that is not one of its own is INVREQ 50 (ASSUMED: IBM does not say whether a token is valid in a
  task that did not receive it; tokens are per task here), and a grandchild is dispatched at its parent's wait,
  completing at that instant plus its own DELAYs on its parent's clock, so the child completes at its own dispatch plus
  every wait it made (a FETCH ANY at the root sees a child that fetched a slow grandchild as slow). A child that never
  waits ends with its children not run, as a parent does (a parent that never FETCHes cannot tell, SPEC 4). The nested
  events are the child's own, in its CHILD event: its RUN, its CHILD events (the grandchildren it dispatched) and its
  FETCH / FREE CHILD, compared as a whole. EIBTASKN of a descendant is its parent's plus its RUN number (a stated
  fact, as at the first level: two tasks at different depths may share one number). The depth is bounded at 3
  generations below a task (child, grandchild, great-grandchild; a RUN from a task at depth 3 is refused by name; IBM
  states no bound). Both sides: `ggcics.c` (a child process forks its own children, `$GGCICS_DEPTH`) and CicsTask
  (`runTransid`, `dispatchChildren`). Pinned by `test_cics_runtimes.py` `nested-*` schedules (both runtimes, one
  script: unfetched, fetched, two grandchildren and their completion order at the root, FETCH CHANNEL of a
  grandchild, TRANSIDERR, an abended grandchild, NOSUSPEND, TIMEOUT, a tie, a foreign token, FREE CHILD, depth 3 and
  the depth cap) and by the case `asynccc-asyncpnt` (ASYNCPNT's STUS child CSSTATS2 RUNs GETP / SPND).
  A START's FROM bytes travel in the region's page, as a TS item's (#4528).
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run
  time): a FETCH whose answer turns on a child completing at the very instant its parent resumed (a tie); FETCH TIMEOUT
  outside 0 to 4080000 ms (IBM's FETCH ANY and FETCH CHILD pages differ); a second FETCH CHILD of a fetched child (INVREQ
  51 is for its channel), FREE CHILD of a fetched one, FETCH CHANNEL of a child that left no current channel; a child
  that went on after an abend (HANDLE ABEND: its completion status); a dispatched child's command on a region resource
  or a terminal (only RETURN / ABEND / LINK / XCTL, and its own RUN / FETCH / FREE CHILD and its children's CHILD, are
  recorded; ENQ / DEQ / counters / SQL, which leave no event, are refused when the case is built) and a RUN TRANSID
  3 generations below the issuing task (a great-great-grandchild: the depth the harness states); a child whose transaction the case runs no
  program for; a DELAY TIME, or a DELAY out of range, in a task with children or in a child; a CHANNEL name starting
  DFH; an undefined transaction together with an incorrect CHANNEL name (which condition comes first); START CHANNEL of
  a channel not in scope; START USERID / SYSID / NOCHECK / ATTACH / BREXIT / FMH; RETRIEVE SET (a pointer)
  and WAIT; CANCEL of anything but a REQID. At run time: a START LENGTH past FROM's end (X6); a REQID that exists
  other than this task's own with FROM, reused with FROM; RETRIEVE INTO for a record whose START gave no FROM
  (whether that is ENVDEFERR); any RETRIEVE after ENVDEFERR (whether the record was used up); a RETRIEVE in a RUN
  child. The default abend codes of TRANSIDERR / TERMIDERR / IOERR / ENVDEFERR are not modelled: a program reaching
  one unhandled stops.
- **Reached.** cics-crucible gt-start-retrieve (6) and gt-terminal-coalesce (4) on the det port as on cobol-stub, and
  gt-start-options (7: data options, ENVDEFERR, RETRIEVE with no INTO, AFTER / AT and TIME(250000), INVREQ RESP2 6 / 5
  / 6 / 4, REQID IOERR, RUN TRANSID and its TRANSIDERR), cobol-stub and the det port both passing the hand-written
  logs (crucible branch `cases/start-retrieve-4270`, squid-protocol/cics-crucible#7, not yet released or pinned).
  **#4950:** the child schedule is pinned on both runtimes by one set of step scripts (`test_cics_runtimes.py`:
  completion order, NOSUSPEND before and after a wait, a waiting FETCH, TIMEOUT running out, FREE CHILD, an abended
  child, a tie, a child's region-resource command, channel names); every port that DELAYs re-proved. CBSA CRECUST's
  credit check (five RUN children, DELAY 3 seconds, FETCH ANY NOSUSPEND x6) runs on the oracle, but the program is not
  provable: its CEEDAYS passes a 10-byte picture over an 8-byte 'YYYYMMDD' (refused, L1). **#4952:** the case is
  `tests/equivalence/cbsa-crecust` (Db2 seed, five RUN children). The scenario `born-before-1601` (the date-of-birth
  check ends before its CEEDAYS call) runs the children and the six FETCH ANYs and, run alone through det_port, has
  all 18 events equal on both runtimes; that is not a proof of the program (13/37 paragraphs), and the committed case
  is refused by name on `create-customer` / `born-in-the-future` until L1 is settled. Holes of the program: L1 (the
  CEEDAYS picture and date strings overrun their 8 bytes by 2), L4 (`FC` is 8 bytes, LE's token 12) and this
  entry's ASSUMED schedule. BNK1CCS, which LINKs CRECUST, is not proven while they stand.

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
  (no security, nobody signs on), FACILITY the task's terminal, screen 24 x 80. The equivalence harness states the
  ones a case gives (#5126): a scenario's or the case's `"userid"` (`$GGCICS_USERID` / `withUserid`), `"screen"`
  (`[rows, columns]`, of a stated `"termid"`: `$GGCICS_SCREEN` / `withScreen`), `"termid"` (FACILITY) and `"startcode"`;
  `proof_blockers` drops the gap only when every scenario states it. Unstated, the option is refused at run time, not
  guessed.
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

### X22. READ GTEQ / GENERIC, DELETE GENERIC — ASSUMED, REFUSED where IBM is silent or the layout decides (#4270, #4771)
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
- **#4771 (zECS ZECS000 / ZECS003): a file named at run time, and DELETE GENERIC.** zECS names its cache file by a data
  item (`ZF-FCT`: 'ZC' + the transaction's last two characters + 'FILE', ZC##FILE instantiated per table by the install
  JCL), so no file is known when translating. READ GTEQ on the full key then searches with the key length of the store
  the name picks at run time (the project's stores, by name; a name it stores none for is a Hole then, as for every
  other command on such a file), and a RIDFLD shorter than that key is refused then (X6). DELETE GENERIC (IBM, EXEC
  CICS DELETE, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-delete: GENERIC "Specifies that the search key is a
  generic key with a length specified in the KEYLENGTH option"; KEYLENGTH and RIDFLD required with it; NOTFND RESP2 80
  "An attempt to delete a record based on the search argument provided is unsuccessful"; INVREQ 25 / 42 as READ's):
  every record whose key starts with RIDFLD's first KEYLENGTH bytes is deleted (the page's "same starting characters";
  IBM: "delete a group of records with a single invocation"; ASSUMED: no record is locked by another task, so none is left behind (IBM's LOCKED / RECORDBUSY outcomes, a single-task run never meets them), and the generic delete is not a non-KSDS one, INVREQ RESP2 22, the stores being KSDS), NOTFND RESP2 80 when none.
  The stub: `GGCDELT` with GG-FLAGS `GENERIC`; the det port: `CicsTask.delete` over repeated `DetCics.Store.search` /
  `remove`. Refused: a GENERIC KEYLENGTH not shorter than the key or not above zero (IBM: RESP2 25 at or above the full key; zero "unpredictable", RESP2 42 below zero) (here when the file is known, at
  run time when it is named then), a KEYLENGTH that is no constant, NUMREC (no corpus program asks for the count).
  Pinned by `test_read_gteq_on_a_file_named_at_run_time_takes_that_files_key`,
  `test_delete_generic_deletes_every_record_with_the_generic_key`, `test_a_delete_generic_is_named_to_the_stub` and the
  runtime tests (`test_the_stub_delete_generic_*`, `test_cics_task_delete_generic_*`). No case runs zECS's file yet: the
  estate must state which table's file (ZCnnFILE) a case runs, the open half of #4771.
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
  other options (REDUCE, COMPAREMIN / COMPAREMAX, NOSUSPEND) are X53's since #5039.
- **GET DCOUNTER INCREMENT [WRAP]** (#4767, zECS ZECS001; same page, "summary-get-counter-get-dcounter"). "VALUE returns the current
  number ... the counter is incremented after the current number has been assigned"; INCREMENT "the amount to add; the default is 1";
  DCOUNTER's value is "a doubleword unsigned binary"; WRAP: "if the counter is at its limit, the server resets it to its minimum
  value"; without REDUCE or WRAP a counter at its maximum is SUPPRESSED RESP2 101 and "the current number is not changed". Modelled
  (`CicsTask.getCounter(pool, name, increment)`, the stub's `GGCGDCN`, writing VALUE big-endian into 8 bytes): the value before the
  increment, then the counter is INCREMENT more (default 1); INVREQ 201 / 403 / 404 as GET COUNTER. **What IBM leaves open, and
  what we do.** (1) The counter's maximum and minimum are not stated by the run (DEFINE refuses MINIMUM / MAXIMUM, above), so WRAP
  and SUPPRESSED RESP2 101 cannot be decided: WRAP is accepted and changes nothing; a counter that would pass 4294967295 (the smallest
  maximum the page leaves open) and an INCREMENT not above zero (the page gives it no meaning; the doubleword is unsigned) are
  REFUSED at run time. (2) A stated counter is one number whichever form names it (ASSUMED: IBM does not say whether a COUNTER and a
  DCOUNTER of one name are the same counter). (3) The INCREMENT is a data area (an 8-byte unsigned binary in zECS); a literal is
  refused by the stub translator, and INCREMENT / WRAP on the fullword form COUNTER are refused. REDUCE, COMPAREMIN, COMPAREMAX and
  NOSUSPEND: X53 (#5039). Unit-proven on both runtimes line for line (tests/cics_crucible/test_cics_runtimes.py) and both translators;
  no case runs it yet (zECS ZECS001's 4000-GET-COUNTER does, after its CALL ZUIDSTCK, which the corpus does not ship).
- **Not modelled / unobserved**: RESP2 of a command that completed is 0 (IBM states none: the case logs RESP2 only for a failed
  command); the order of 403 and 404 when both a pool and a counter name are invalid (the case never provokes both; the runtimes
  check the pool first); the value area of a failed GET / QUERY (not written).
- **Superseded in part by X45** (#4770): DEFINE / QUERY / DELETE DCOUNTER, MINIMUM / MAXIMUM on the doubleword form and WRAP at a
  counter's limits are modelled there; the limits (1) of GET DCOUNTER above hold only for a counter with no limits entry.
- **Superseded in part by X50** (#5039): DEFINE / QUERY COUNTER MINIMUM / MAXIMUM, GET COUNTER INCREMENT and WRAP at a fullword
  counter's limits are modelled there; the limits (1) of GET COUNTER above hold only for a counter with no limits entry.
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
  now translates whole. An equivalence case states its mapsets the same way (`"maps": {MAP: {"mapset": MAPSET}}`,
  `equivalence_cics.mapsets_env`, #5076: cbsa-bnk1ccs's CLEAR abends ABM0 on the COBOL side and in the port); a case with no `maps`
  checks nothing.
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
  left alone (ASSUMED; they are written on NORMAL only). **Refused by name**: (the direct form INQUIRE URIMAP(name) was, until #4768: now X34),
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

### X34. INQUIRE URIMAP(name), the direct form, and INQUIRE PROGRAM STATUS — ASSUMED, REFUSED where IBM is silent (#4768, zECS)
- **INQUIRE URIMAP, the direct form** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-urimap). The command
  names a definition, "URIMAP(data-value) specifies the name (1 - 8 characters) of the URIMAP definition about which you are
  inquiring", unless a browse option is given. Conditions: NOTFND RESP2 3 "The URIMAP cannot be found"; NOTAUTH RESP2 100 (no
  security in the region). PATH and TRANSACTION as for the browse (X32). Modelled (`CicsTask.inquireUrimap`, the stub's
  `GGCURIB` with GG-FLAGS `DIRECT`): the definition among the installed URIMAPs the run states (the case's "urimaps" / the case
  CSD's DEFINE URIMAPs, `CicsTask.withUrimaps` / `$GGCICS_URIMAPS`), the name compared as written, blanks trimmed; PATH and
  TRANSACTION padded and left alone on any condition as X32 states.
- **What IBM leaves open, and what we do.** (1) Whether a direct INQUIRE moves an open browse: IBM's browse pages describe the
  browse cursor only; we leave it where it was (ASSUMED: the direct form is not a browse step). (2) TRANSACTION for a definition
  with none (a CLIENT URIMAP): blanks, as X32's browse (ASSUMED). (3) The definitions themselves: stated, never guessed; unstated,
  both runtimes stop the run (REFUSED, as X32).
- **INQUIRE PROGRAM STATUS** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-program). STATUS "Returns a CVDA
  value indicating whether the program is available for use": ENABLED or DISABLED. The definition's STATUS attribute (DEFINE
  PROGRAM, https://www.ibm.com/docs/en/cics-ts/6.x?topic=resources-program-attributes) is ENABLED by default. Modelled
  (`CicsTask.programStatus`, the stub's `GGCINQP` leaving the CVDA in GG-NUM): ENABLED (23) for every program the region
  defines, written on NORMAL only (PGMIDERR, and a condition a fault plan injects, leave the area alone). No harness states a
  DISABLED definition: the cics-crucible runner refuses a case whose CSD defines a program STATUS(DISABLED) (every cell
  unsupported, by name), since a disabled program would also change LINK / XCTL, which nothing models. Every other INQUIRE
  PROGRAM attribute (CEDFSTATUS, LANGUAGE, ...) stays refused by name.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven on `CicsTask` and the stub C
  (tests/cics_crucible/test_cics_runtimes.py); both translators (tests/cobol_mainframe/test_det_translate.py,
  test_equivalence_cics.py). zECS: the INQUIRE URIMAP holes of ECS001, ZECS000 and ZECS003 and ZECS001's INQUIRE PROGRAM STATUS
  translate; no program is whole from this alone (WEB, #4767).

### X35. WEB OPEN, WEB CONVERSE, WEB CLOSE (CICS web support, HTTP client) — ASSUMED, REFUSED where IBM is silent (#4767, zECS)
- **WEB OPEN** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-open). SESSTOKEN "an 8-byte binary value that uniquely
  identifies this application's use of the connection"; HOST "the hostname of the server", HOSTLENGTH its length; PORTNUMBER "For
  HTTP, the default port number is 80, and for HTTPS, the default port number is 443"; SCHEME HTTP or HTTPS; URIMAP "a URIMAP
  definition that provides" scheme, host, port and path (USAGE(CLIENT)), "do not also specify CERTIFICATE, HOST, HOSTLENGTH,
  PORTNUMBER ... or SCHEME". Conditions modelled: LENGERR RESP2 21 "Incorrect host length" (HOSTLENGTH not above zero), INVREQ
  RESP2 40 "Scheme incorrect" (a CVDA other than HTTP / HTTPS), INVREQ RESP2 138 "The port number is greater than 65535".
  Modelled (`CicsTask.webOpenHost` / `webOpenUrimap`, the stub's `GGCWOPN`): a session to the stated peer of that scheme, host
  (compared without case, ASSUMED) and port, or whose CLIENT URIMAP that is; the token goes to the area on NORMAL only.
- **WEB CONVERSE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-converse). METHOD's CVDAs; "CICS blocks a body for
  methods that disallow it and requires one for methods that need it" (INVREQ 33 / 34); PATH "If WEB OPEN specified a URIMAP, that
  URIMAP's path is the default"; QUERYSTRING's leading "?" "is optional"; MEDIATYPE "For requests that require a body, you must
  specify" it (INVREQ 76); MAXLENGTH "the maximum amount ... of data that CICS is to pass to the application", without NOTRUNCATE
  "excess data is discarded and LENGERR RESP2 57"; TOLENGTH "set to the amount of data that CICS has returned"; STATUSCODE "a
  binary halfword"; STATUSTEXT the reason phrase, STATUSLEN its area's length (LENGERR 58 when longer; 59 when not above zero).
  Conditions modelled: NOTOPEN 27 (a token that is no open session's), INVREQ 33, 34, 54 (a METHOD value that is no method), 76,
  LENGERR 5, 8, 16 (MAXLENGTH below zero), 50, 57, 59. Modelled (`CicsTask.webConverse`, the stub's `GGCWCNV`): the request sent
  is recorded (event WEB-CONVERSE: host, method, path, query without its "?", and the media type and body when there is a body,
  RESP / RESP2) and answered by the first stated response not yet given that matches its method, path and query.
- **WEB CLOSE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-close). NOTOPEN RESP2 27 "Invalid session token"; after
  it "the session token is no longer valid". Modelled (`CicsTask.webClose`, the stub's `GGCWCLS`).
- **What IBM leaves open, and what we do.** (1) The server: STATED, never guessed (the case's or scenario's `http_peers`,
  `CicsTask.withHttpPeers` / `$GGCICS_HTTP`); a connection to a server, or a request, the run does not state is refused. (2) The
  token's value: ours, `GGWS` and a 4-digit sequence per task (ASSUMED: IBM only says 8 bytes). (3) Code-page conversion: the
  exchange is stated and recorded in the program's own characters, so CLIENTCONV and its CVDAs (CLICONVERT, NOINCONVERT,
  NOOUTCONVERT, NOCLICONVERT) change nothing within the model (ASSUMED: the stated response is what reaches the program's area);
  CHARACTERSET, BODYCHARSET and CODEPAGE are refused. (4) MAXLENGTH omitted: INTO's length (ASSUMED, as the COBOL translator
  supplies a data area's length for its length options). (5) TOLENGTH on LENGERR 57: the bytes returned, MAXLENGTH (ASSUMED);
  INTO, TOLENGTH, STATUSCODE, STATUSTEXT and MEDIATYPE are written on NORMAL and LENGERR 57 only, left alone otherwise
  (ASSUMED). (6) STATUSTEXT: the phrase's bytes only, the rest of the area left alone (ASSUMED); a phrase longer than STATUSLEN
  is REFUSED (LENGERR 58 is listed but not what the area then holds). (7) MEDIATYPE received: blank-padded to 56 (ASSUMED); sent
  only with a body (ASSUMED: a GET has no Content-Type). (8) The order of conditions: IBM does not order them, so two at once are
  REFUSED. (9) MAXLENGTH 0, a PORTNUMBER below 1, TRACE / OPTIONS (OPTIONS' body rules are open), a session opened by HOST with
  no PATH (IBM gives no RESP2), a body with a blank MEDIATYPE: REFUSED. (10) A length past its area (HOSTLENGTH, PATHLENGTH,
  QUERYSTRLEN, FROMLENGTH) or a response longer than INTO / a phrase longer than STATUSTEXT's area: REFUSED, as X6 (GnuCOBOL lays
  out the storage that follows unlike IBM's compiler).
- **Refused by name** (the translators): CERTIFICATE, CODEPAGE, HTTPVNUM / HTTPRNUM, CIPHERS on OPEN; URIMAP, DOCTOKEN,
  CONTAINER, SET, NOTRUNCATE, TOCONTAINER, ACTION, CLOSESTATUS, AUTHENTICATE / USERNAME / PASSWORD, CHARACTERSET, BODYCHARSET on
  CONVERSE, and a CONVERSE without INTO; WEB SEND / RECEIVE / PARSE URL / EXTRACT / READ / WRITE HTTPHEADER stay refused whole.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven: `CicsTask` and the stub C answer one list of steps
  line for line and refuse the same steps (tests/cics_crucible/test_cics_runtimes.py); both translators
  (tests/cobol_mainframe/test_det_translate.py, test_equivalence_cics.py); the equivalence harness states the peers on both sides
  and compares the requests (test_equivalence_cics.py). No cics-crucible case yet (its SPEC has no WEB-CONVERSE event: a crucible
  SPEC change). zECS: with #4768's INQUIRE URIMAP direct form, ECS001 translates whole.

### X36. WEB PARSE URL (CICS web support, a URL taken apart) — ASSUMED, REFUSED where IBM is silent (#4767, zECS)
- **WEB PARSE URL** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-parse-url). URL "the complete URL string",
  URLLENGTH its length; SCHEMENAME "always returned in uppercase" (a 16-character area); HOST "host name or IP address",
  HOSTLENGTH the buffer size on input and "set to the returned length"; PORTNUMBER "the explicit port, otherwise the default for
  the scheme" (80 HTTP, 443 HTTPS); PATH, PATHLENGTH; QUERYSTRING "returned in escaped form", QUERYSTRLEN; escape sequences are
  checked ("%" followed by two hexadecimal characters 0-9, A-F); "not checked: that the host exists or that characters are
  permitted in a URL". Conditions modelled: INVREQ RESP2 28 "Incorrect URL", INVREQ RESP2 65 "Bad escape sequence". Listed and
  REFUSED when they occur: LENGERR RESP2 8 / 29 / 30 (query / host / path longer than its length): IBM says the data is
  truncated but not what the length option then holds. Modelled (`CicsTask.webParse`, the stub's `GGCWPRS`; the det and
  stub translators read the option rules from the spec): the URL's first URLLENGTH bytes are parsed.
- **What IBM leaves open, and what we do.** (1) What makes a URL "incorrect": ASSUMED INVREQ 28 for no "scheme://" or an empty
  scheme, an empty host, and a port that is not 1 to 5 digits or above 65535 (IBM lists no condition for a bad port). (2) The
  pieces: the path keeps its leading "/", the query loses its "?" (ASSUMED: IBM's WEB CONVERSE takes PATH and QUERYSTRING the
  same way); the host is returned as written, without case folding (ASSUMED). (3) Areas are written on NORMAL only and only the
  piece's bytes (the rest of the area is left alone), SCHEMENAME blank-padded to its area (ASSUMED). (4) A PATH or QUERYSTRING
  asked for when the URL has none (zECS gives "http://host:port"): REFUSED, IBM does not say what the area and its length hold.
  (5) REFUSED: a scheme other than HTTP / HTTPS (IBM says only those two are "supported for use with WEB OPEN" but not whether
  the parse rejects the rest), a user-info part ("@"), a fragment ("#"), an IPv6 host (brackets and HOSTTYPE), an empty port
  ("host:"), port 0, a lowercase hex digit in an escape (IBM lists 0-9, A-F), a URLLENGTH not above zero (no condition is
  listed), a URLLENGTH or HOSTLENGTH / PATHLENGTH / QUERYSTRLEN past its area (as X6: GnuCOBOL lays out the storage that follows
  unlike IBM's compiler), two conditions at once (IBM does not order them, as X35). (6) The URL is parsed in the program's
  characters: no code-page conversion is modelled.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven: `CicsTask` and the stub C answer one list of steps
  line for line and refuse the same steps (tests/cics_crucible/test_cics_runtimes.py); both translators
  (tests/cobol_mainframe/test_det_translate.py, test_equivalence_cics.py). The command writes no event, so no harness change
  and no crucible SPEC change. zECS: ZECS000, ZECS001 and ZECS003 each parse the partner data center's "http://host:port" with it.

### X37. WEB SEND (CICS web support, the server's response) — ASSUMED, REFUSED where IBM is silent (#4767, zECS)
- **WEB SEND (server)** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-send-server). "Sends a response when the application is in
  the server role"; "only one response can be sent per task"; FROM the body (FROMLENGTH required, "must be greater than zero"); MEDIATYPE
  a 56-byte area, up to 56 characters with no spaces, "CICS checks the format but not validity" and gives no default; STATUSCODE
  "defaults to 200" (204, 205 and 304 allow no body); STATUSTEXT the reason phrase with STATUSLEN; ACTION IMMEDIATE sends at once,
  EVENTUAL "sends at end of task" and is the default for non-chunked sends; after an IMMEDIATE send "the second attempt returns
  an error", after an EVENTUAL one the second response replaces the first; SRVCONVERT converts the body and "the media type must
  be text per IANA", else INVREQ RESP2 46. Conditions modelled: INVREQ RESP2 11 "Action code invalid", INVREQ RESP2 72 "Status
  code does not support a message body". Modelled (`CicsTask.webSend`, the stub's `GGCWSND`): the response sent is recorded
  (event WEB-SEND: status, reason phrase, media type, body, action, RESP / RESP2) and compared; a send with a condition records
  nothing.
- **What IBM leaves open, and what we do.** (1) The inbound request: STATED, never guessed (the case's or scenario's
  `http_request`, `CicsTask.withHttpRequest` / `$GGCICS_WEBREQ`); a WEB SEND without it is refused (IBM's INVREQ RESP2 1, "issued
  in a non-CICS Web support application", is not what an unstated fact means). Only that a request is stated is read today: WEB
  RECEIVE, WEB EXTRACT and WEB READ HTTPHEADER (ZECS001, ZECS003's receiving side) stay refused whole until they read it. (2) The
  default reason phrase when STATUSTEXT is omitted, and the Content-Type when MEDIATYPE is omitted ("no default"): recorded as
  none (ASSUMED: nothing is sent). (3) STATUSLEN omitted: the whole STATUSTEXT area (ASSUMED, as IBM's COBOL translator supplies a
  data area's length for a length option; zECS omits it). (4) The response is in the program's own characters: SRVCONVERT /
  NOSRVCONVERT change nothing within the model (ASSUMED); CHARACTERSET, CLNTCODEPAGE and HOSTCODEPAGE are refused. (5) REFUSED:
  a second send after IMMEDIATE (no RESP2 is given), FROMLENGTH or STATUSLEN not
  above zero (IBM lists both LENGERR 50 and INVREQ 131 for a zero FROMLENGTH), a STATUSCODE outside 100-599 (INVREQ 87's "not
  allowed" is not defined), a blank MEDIATYPE or one that is not `type/subtype` of printable characters (the format check is
  not defined), SRVCONVERT on a media type that is not `text/*` (IBM's IANA list is not stated: INVREQ 46 is not modelled), a
  length past its area (as X6: GnuCOBOL lays out the storage that follows unlike IBM's compiler), two conditions at once (IBM
  does not order them, as X35).
- **WEB SEND ACTION(EVENTUAL) and the omitted ACTION** (#4941; `CicsTask.webSendBody`, the stub's `web_send_body` and `web_flush`). IBM:
  "EVENTUAL sends the response to the Web client at end of task", "For message sends that do not use chunked transfer-coding, EVENTUAL is
  the default" (chunking is refused, so an omitted ACTION is EVENTUAL), "One response only can be sent during a task", a second send after
  IMMEDIATE returns an error and after EVENTUAL "the second response overwrites the components of the previous response" (and, in the same
  text, "The first response is lost, and the second response is sent"). Modelled: the response is held; a second EVENTUAL send replaces it;
  at the end of the task (`CicsTask.events()` once the task ended, the stub's `GGCEND`) one WEB-SEND event is recorded with action EVENTUAL,
  after the task's RETURN event. A send that ended in a condition (INVREQ 11 / 72 / 143, NOTFND 1) leaves a held response as it was
  (ASSUMED). ASSUMED: the two IBM sentences are read as the second response replacing the whole first (no component is carried over). ASSUMED:
  the response is sent after the RETURN event (IBM says only "at end of task"). REFUSED: an IMMEDIATE send after an EVENTUAL one (IBM allows
  one response and says only what a second EVENTUAL does), a task that ended in an abend with a response held (IBM does not say whether it
  is sent), a WEB WRITE HTTPHEADER after any send (IBM does not say whether a header written after an EVENTUAL send joins the held response).
- **WEB SEND DOCTOKEN** (#4767, ZECS001's 9700-STATUS-204; `CicsTask.webSendDocument`, the stub's `GGCWSDC`): the response body is the document the
  task created, as it is when sent (the program's characters), FROM / FROMLENGTH not given; an empty document is no message body (ASSUMED: IBM lists
  INVREQ RESP2 72 for 204 / 205 / 304 "with a body" and does not say what an empty document is), so a 204 may send it and records an empty body. A token
  that names no document (never created, or deleted) is NOTFND RESP2 1 (IBM: "the document has not been created, or has been deleted, or the
  name is incorrectly specified", one RESP2 for all three). **DOCSTATUS** (#4941): "indicates whether the document should be deleted or not
  deleted during processing of the WEB SEND command"; DOCDELETE: "CICS deletes the document after the document contents are saved for
  sending", "subsequent requests for the document ... generate a NOTFND response" (DOCUMENT RETRIEVE and WEB SEND DOCTOKEN answer NOTFND 1);
  NODOCDELETE, "the default value", keeps it; any other value is INVREQ RESP2 143. IBM's page does not say which ACTION values DOCSTATUS
  works with: it is modelled for both (ASSUMED) and refused without DOCTOKEN (a FROM send has no document). DOCSTATUS is a CVDA (DOCDELETE
  295, NODOCDELETE 296); the document is deleted only by a send that succeeds.
- **WEB SEND CONTAINER / CHANNEL** (#5037; `CicsTask.webSendContainer`, the stub's `GGCWSCT`): the response body is the container's data
  as it is when sent. IBM: CONTAINER "specifies the name of the container where the HTTP body is held", "If the CONTAINER option is
  specified, CHANNEL is optional", CHANNEL "specifies the name of the channel to which the container belongs", omitted: "CICS assumes
  the current channel". Conditions: CONTAINERERR RESP2 2 ("The container specified by the CONTAINER option could not be found"),
  CHANNELERR RESP2 2 ("The channel specified by the CHANNEL option could not be found"), INVREQ RESP2 145 ("Channel was not
  specified, and there is no current channel"), INVREQ RESP2 150 ("Conversion requested, but data to be sent is in a DATATYPE BIT
  container"; IBM: "if you code either the SRVCONVERT or CHARACTERSET options with a BIT container, an INVREQ RESP2 error is
  produced"). Everything else is the FROM send's (status, media type, ACTION, STATUSCODE 204 / 205 / 304 with a body INVREQ 72, the
  held EVENTUAL response). REFUSED (IBM is silent): CONTAINER together with FROM or DOCTOKEN (IBM does not say what two bodies mean),
  CHANNEL without CONTAINER, an empty container (IBM does not say what an empty body is; DOCTOKEN's empty document is the ASSUMED
  case, a container is not), a DATATYPE BIT container sent without conversion (the bytes are not compared as text), a container named
  with a character IBM does not allow or a channel an XCTL left behind (X17), and DFHTRANSACTION (not modelled, X17). IBM's own
  "do not specify CHUNKING / HOSTCODEPAGE with CONTAINER" is kept: both are refused whole.
- **CHUNKING** stays refused by name: a chunked response is a sequence of sends (CHUNKYES ... CHUNKEND; IBM: "the transaction is abended
  with abend code AWBP" if one fails, RESP2 77 / 85 / 86 / 89-95 / 120-129) and IBM gives no rule for what the client sees if the
  task ends with a chunk open.
- **CHARACTERSET / CLNTCODEPAGE / HOSTCODEPAGE** stay refused: IBM says "If you omit all of the code page conversion options, no code
  page conversion takes place", "When the CHARACTERSET option is specified, SRVCONVERT is assumed" and names no table, only that
  "CICS does not support all the character sets named by IANA" (RESP2 7 / 83 / 88 / 147 are conversion outcomes). CLNTCODEPAGE is
  "supported for upgrade purposes only" (CHARACTERSET replaces it). CLOSESTATUS (IBM: "The default is that the connection is not
  closed"; RESP2 13) is the connection's, which the model has no state for.
- **Refused by name** (the translators): CHUNKING, CHARACTERSET, CLNTCODEPAGE, HOSTCODEPAGE, CLOSESTATUS, LENGTH; a
  WEB SEND without FROM or FROMLENGTH; DOCSTATUS without DOCTOKEN.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven: `CicsTask` and the stub C answer one list of steps
  line for line, record the same event and refuse the same steps (tests/cics_crucible/test_cics_runtimes.py); both translators
  (tests/cobol_mainframe/test_det_translate.py, test_equivalence_cics.py); the equivalence harness states the request on both
  sides and compares the response. The deferred send, DOCSTATUS and WEB RETRIEVE's NORMAL outcome are proven on both runtimes line for line
  (tests/cics_crucible/test_cics_runtimes.py, `_X41_CASES`). No cics-crucible case yet (its SPEC has no WEB-SEND event: a crucible SPEC change). zECS:
  ZECS003's one WEB SEND (FROM / FROMLENGTH / MEDIATYPE / ACTION IMMEDIATE / STATUSCODE / STATUSTEXT / SRVCONVERT) is modelled.

### X38. WEB EXTRACT / EXTRACT WEB, EXTRACT TCPIP, WEB RECEIVE, WEB READ / WRITE HTTPHEADER, WEB READ FORMFIELD / QUERYPARM and the WEB browse forms (CICS web support, the server reading its request) — ASSUMED, REFUSED where IBM is silent (#4767, #4940, #4972, zECS)
- **WEB EXTRACT** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-extract), server form. HOST "host component of the URL, from the
  Host header or an absolute URI", HOSTLENGTH "buffer length supplied, set to the length of the data returned"; HTTPMETHOD /
  METHODLENGTH, HTTPVERSION / VERSIONLEN ("1.1" indicates HTTP/1.1, "1.0" HTTP/1.0 or lower), PATH / PATHLENGTH, QUERYSTRING /
  QUERYSTRLEN ("returned in escaped form"), PORTNUMBER ("if absent, CICS derives it from the scheme: 80 HTTP, 443 HTTPS"),
  SCHEME (CVDA HTTP / HTTPS), REQUESTTYPE (HTTPYES "an HTTP request"). Conditions modelled: LENGERR RESP2 5 / 7 / 21 (PATHLENGTH /
  VERSIONLEN / HOSTLENGTH not greater than zero). Listed and REFUSED when they occur: LENGERR RESP2 4 / 6 / 8 / 29 / 30 (a
  piece longer than its length: IBM truncates but not what the length option then holds, as X36).
- **WEB RECEIVE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-receive-server), buffer form. "If the INTO option is
  specified, MAXLENGTH must also be specified, with a value greater than zero" (INVREQ RESP2 16 otherwise: REFUSED when
  translating, the spec's `requires`); LENGTH "the amount of data returned"; MAXLENGTH "maximum amount of data passed to the
  application"; "if the NOTRUNCATE option is not specified, any further data present in the message has now been discarded"
  (LENGERR RESP2 57 "body exceeds the length specified and the remainder was discarded"; LENGERR RESP2 16 "MAXLENGTH less than or equal
  to zero"); MEDIATYPE "a 56-byte area". SRVCONVERT converts a text body from the client's character set, NOSRVCONVERT does not.
- **WEB READ HTTPHEADER** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-read-httpheader). "VALUELENGTH: you supply the
  buffer length, and CICS sets it to the actual length of the data returned"; conditions (server): INVREQ RESP2 43 "no HTTP headers
  found", NOTFND RESP2 1 "no header with the given name was found", LENGERR RESP2 1 "VALUELENGTH not greater than zero", LENGERR
  RESP2 2 "value truncated because the receiving buffer is too small".
- **WEB WRITE HTTPHEADER** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-write-httpheader). "Each command adds a single
  header"; a header written twice: "CICS adds the new header ... in addition to the existing header"; LENGERR RESP2 35 "NAMELENGTH
  not greater than zero", RESP2 55 "VALUELENGTH not greater than zero or greater than 32000". A header CICS would also generate is
  not overwritten (the response CICS builds is not modelled: X37 records only what the program sent).
- **What IBM leaves open, and what we do.** (1) The request is a fact STATED, never guessed (X37's `http_request`, now read by every
  command; an unstated one is refused). The stated `version` is exactly what HTTPVERSION returns (ASSUMED: IBM's text says "1.1"
  indicates HTTP/1.1 without saying which characters CICS returns); the stated `port` is what PORTNUMBER returns (the scheme's
  default when the request has none is the run's to state). (2) A request with no query string: QUERYSTRLEN 0 and the area left
  alone, NORMAL (ASSUMED: IBM lists NOTFND RESP2 155 for "request line information not found" and no other case). (3) Areas are
  written on NORMAL only, a piece's bytes only (the rest of the area is left alone), as X36; MEDIATYPE is blank-padded to its
  56 bytes. (4) The body is in the program's characters whatever the conversion option (ASSUMED, as X37); code-page options, TYPE
  and SERVERCONV (its values are not documented) are refused. (5) REFUSED: NOTRUNCATE (SET, a body in CICS storage, is modelled by X47), TOCONTAINER / TOCHANNEL, the client forms (SESSTOKEN, REALM / REALMLEN),
  HOSTTYPE, URIMAP; a WEB RECEIVE of a request with no body (IBM does not say what INTO, LENGTH and MEDIATYPE then hold) and a
  second WEB RECEIVE (IBM does not say what a body already received returns again); a header read whose name matches a stated one
  only without case (IBM does not say whether names compare with case) and two stated headers of the name; a value longer than
  VALUELENGTH (LENGERR RESP2 2: what VALUELENGTH then holds is not stated); a NAMELENGTH not above zero on READ (listed for a client
  only), METHODLENGTH / QUERYSTRLEN not above zero (no condition is listed); a header written after WEB SEND (IBM does not say what
  a header after an IMMEDIATE response means), a header name that is blank or holds a blank or a colon (IBM does not define the
  check); every length past its area (as X6: GnuCOBOL lays out the storage that follows unlike IBM's compiler); two conditions at
  once (IBM does not order them, as X35).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven: `CicsTask` and the stub C answer one list of steps line
  for line, record the same WEB-HEADER events and refuse the same steps (tests/cics_crucible/test_cics_runtimes.py, four request
  fixtures x every option class); both translators (tests/cobol_mainframe/test_det_translate.py, test_equivalence_cics.py). No
  cics-crucible case (its SPEC has no WEB event). zECS: ZECS001's WEB EXTRACT, its first WEB RECEIVE form's MEDIATYPE / LENGTH /
  MAXLENGTH, WEB READ HTTPHEADER(Authorization) and WEB WRITE HTTPHEADER are modelled; its WEB RECEIVE SET is modelled by X47 (the pointer lane).

## #4940: WEB READ FORMFIELD / QUERYPARM and the WEB browse forms

Sources: https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-read-formfield, `-web-read-queryparm`, `-web-startbrowse-formfield` /
`-queryparm` / `-httpheader`, `-web-readnext-formfield` / `-queryparm` / `-httpheader`, `-web-endbrowse-formfield` / `-queryparm` / `-httpheader`.

- **What IBM says (modelled).** READ FORMFIELD / QUERYPARM: the name "is not case sensitive"; "CICS unescapes any escaped characters before
  placing them in the buffer"; VALUELENGTH is the buffer's size in and "the actual length of the value" out, a longer value "is truncated"
  (LENGERR RESP2 5), a shorter one "placed in the leftmost bytes"; INVREQ RESP2 13 "the HTTP request contains no forms data" / "no keyword
  parameters were supplied", NOTFND RESP2 1, LENGERR RESP2 1 "NAMELENGTH or VALUELENGTH is zero or negative". The browse: a start with a name
  begins "at the named field", without one "at the first name and value pair"; ILLOGIC RESP2 5 (FORMFIELD, QUERYPARM) / 10 (HTTPHEADER) "a browse is
  already in progress", INVREQ RESP2 43 "no HTTP headers", NOTFND RESP2 1, LENGERR RESP2 1. READNEXT: FORMFIELD / HTTPHEADER receives the name "as it is
  stored", each length option "holds the actual length", a name or value that does not fit is LENGERR RESP2 4 / 5 and (FORMFIELD, QUERYPARM) "the next
  execution returns the same field", ENDFILE "all name-value pairs have been read" (no RESP2 listed), INVREQ RESP2 4 "before WEB STARTBROWSE". ENDBROWSE:
  INVREQ RESP2 4 before a start. Form data lives in the request body ("an HTML form that is part of the current task's HTTP request body"), query
  parameters in the query string.
- **ASSUMED (IBM silent).** The data is the stated request's body (a form: media type application/x-www-form-urlencoded) or query string, read as
  name=value pairs joined by '&', split at the first '=' (a value may hold '='), unescaped by %XX only; the browse returns each pair, duplicates
  included, in the order stated, and after a start name runs to the end; a start that raises a condition starts no browse; ENDFILE's RESP2 is 0;
  a LENGERR RESP2 1 READNEXT reads nothing and the browse stays; the three browses and a READ are independent of each other; a start name is
  matched exactly (READ is the only form IBM words as without case). An empty body / query string is "no forms data" (INVREQ RESP2 13).
- **REFUSED (IBM silent), by name.** Two pairs of a name on a READ or a named start (IBM's READ QUERYPARM page names the case open, and the browse is its
  answer); a start name that matches only without case; a body whose media type is not application/x-www-form-urlencoded (IBM's LENGERR RESP2 153 /
  154 do not say how a form type is told; a multipart form, charset parameter or text/plain body); data outside the plain form -- a pair without
  '=' or with an empty name or an empty pair, ';' (a separator IBM does not mention), '+' (IBM does not say it is a blank), an escape that is not %XX
  or that unescapes to a byte outside printable ASCII (code-page conversion is not modelled), an escaped name (IBM does not say whether names are
  unescaped before they are compared), a raw byte outside printable ASCII -- where IBM's INVREQ RESP2 17 / 6 would fire is not stated; a header
  that does not fit on READNEXT (what the lengths hold and whether the browse moves on is not stated for HTTPHEADER); a name and a value both too
  long (which RESP2); a READNEXT after ENDFILE; SET (the pointer lane), CHARACTERSET / CLNTCODEPAGE / HOSTCODEPAGE, the client form (SESSTOKEN),
  a length past its area, two conditions at once (as X35).
- **Status:** unit-proven, `CicsTask` and the stub C answering one step table line for line (tests/cics_crucible/test_cics_runtimes.py,
  `_X4940_CASES`: 21 request fixtures, every condition and refusal above); both translators (tests/cobol_mainframe/test_det_translate.py,
  test_equivalence_cics.py). No cics-crucible case (its SPEC has no event for these reads).

## #4972: EXTRACT WEB and EXTRACT TCPIP

Sources: https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-extract-web ("a synonym of WEB EXTRACT"), `-extract-tcpip`.

- **EXTRACT WEB.** IBM's page lists the options and conditions of WEB EXTRACT and says it "is a synonym of WEB EXTRACT". Modelled as the one
  command: the same options table, `CicsTask.webExtract` / the stub's GGCWEXT, the same refusals; only the messages name the form the program wrote.
- **EXTRACT TCPIP (modelled).** CLIENTADDR / SERVERADDR "client / server IP address, IPv4 dotted decimal", CLIENTNAME / SERVERNAME "as known by
  the Domain Name Server", each with its length option "length of the buffer on input, set to the returned length on output"; CLIENTADDRNU /
  SERVERADDRNU "the IPv4 address in binary"; CLNTIPFAMILY / SRVRIPFAMILY (CVDA IPV4 300); PORTNUMNU "the port, in binary form, that received the
  incoming data"; SSLTYPE (CVDA SSL 1030, NOSSL 1031, CLIENTAUTH 1032, ATTLSAWARE 1205). LENGERR RESP2 1 "specified, but its length field is
  missing or less than or equal to zero"; CLNTNAME "the actual name length, or zero if the DNS does not know the client".
- **ASSUMED (IBM silent).** The connection is a fact the run STATES (`tcpip`, like X37's `http_request`; unstated, the command is refused).
  A client or server name the DNS does not know is a null name: its length option 0, the area left alone, NORMAL (IBM says so for the client;
  the server's is the same ASSUMED). The address number is the signed fullword (a COBOL fullword holds the signed value). A length that is
  not above zero is the LENGERR RESP2 1 whatever the piece's size (the too-small conditions are not also raised).
- **REFUSED (IBM silent), by name.** No connection stated; an address that is not four decimal parts 0-255 without a leading zero (IPv6, which also
  names CLNTADDR6NU / SRVRADDR6NU; IBM's colon-hexadecimal text is not modelled); CLIENTADDRNU / SERVERADDRNU of an address past a signed fullword
  (IBM gives the unsigned value); a SERVERNAME the connection does not state; a name or address longer than its length (LENGERR RESP2 3 / 4 / 6 / 7:
  what the length option and the area then hold is not stated, as X36); PORTNUMBER (the 5-character form: IBM does not say how it is padded);
  AUTHENTICATE, TCPIPSERVICE, PRIVACY, MAXDATALEN (the TCPIPSERVICE definition is not stated by the connection); a length past its area (as X6);
  two conditions at once (as X35); a length option without its area (IBM lists no condition).
- **Status:** unit-proven. `CicsTask` and the stub C answer one grid of steps line for line (tests/cics_crucible/test_cics_tcpip.py: five stated
  connections x every length token alone, in pairs and together x every number option alone and together, against a reference model written from
  IBM's page); both translators (tests/cobol_mainframe/test_det_translate.py, test_equivalence_cics.py). No cics-crucible case (its SPEC has no
  event for these reads) and no end-to-end equivalence case. No burned estate uses either command (det_survey lists neither; zECS uses WEB EXTRACT only).

### X39. A LINKed program XCTLs with the COMMAREA its caller passed — REFUSED, IBM is silent on copy vs caller's storage (#4816)
- **What.** A program LINKed with a COMMAREA addresses its caller's storage (EXEC CICS LINK, COMMAREA: the area is passed by
  address; the linked program's writes are the caller's, #4806). If that program XCTLs passing its DFHCOMMAREA (or a part of it),
  the question is whether the XCTL target addresses the same storage, so that its writes reach the LINK caller after the LINK
  returns, or a copy, so that only the first program's writes do.
- **IBM.** EXEC CICS XCTL, COMMAREA (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-xctl): "the contents of the
  data-area are passed", "In COBOL, you must give this data area the name DFHCOMMAREA in the receiving program". It does not say
  whether the target addresses the sender's storage or a copy, and says nothing of the sender's own DFHCOMMAREA (LENGERR RESP2 28
  mentions data "being copied", which suggests a copy, but the page does not state it). The addressability sentence the issue
  cites ("CICS ensures that any COMMAREA is addressable by the program that receives it, by copying ... if necessary") is about
  where the storage sits, not about whether the target's writes are the sender's.
- **What we do.** REFUSED by name, never assumed: a successful XCTL whose COMMAREA lies inside the DFHCOMMAREA record of a program
  LINKed with a COMMAREA stops the run, "XCTL passing the COMMAREA its LINK caller passed ... not modelled" (the stub:
  `ggcics.c` GGCXCTL, exit 98, so the equivalence harness refuses the case by name; the det port: `DetCics` emits
  `task.xctlOfLinkage()` before the XCTL and `CicsTask.xctl` throws). A failed XCTL (LENGERR, PGMIDERR) is not refused: the
  program goes on. Not refused: an XCTL of the program's own WORKING-STORAGE (no caller storage), an XCTL at level 1 or of a
  task's own start COMMAREA (nobody else addresses it), and the target of an XCTL passing its own DFHCOMMAREA again (a copy of a
  copy: no LINK caller's storage).
- **Model ports (#4956).** A model-port program is LINKed with its caller's DTO object only, no bytes, so `CicsTask.link` marks
  the callee `linkedDto` and `xctl` refuses, by the same name and message, a successful XCTL whose COMMAREA is that DTO or an
  object it holds by reference (a nested group, a table or its element, a list element, a map value, the byte area). A copy
  (a new object), a failed XCTL, level 1 and the XCTL target's own DTO are not refused. Not detectable, so not refused: a
  String or number field passed as the COMMAREA (a value, the same as a copy).
- **Aliases (#4957).** The det port marks an XCTL whose COMMAREA lies inside any LINKAGE 01 record, not only DFHCOMMAREA: a CALLed
  subprogram's USING record (`CALL 'SUB' USING DFHCOMMAREA`) is the LINK caller's storage under another name, and refuses by the
  same runtime check (only when the program was LINKed with a COMMAREA). `SET ADDRESS OF` (direct or through a pointer) is
  translated since #4771 (X47) and its record is a LINKAGE 01 record like any other, so it carries the same mark and refuses
  by the same runtime check; the oracle's `ggcics.c` compares addresses, so it refuses every alias form.
- **Status:** REFUSED. When IBM's reference or a system run settles it, replace the refusal with the model.

### X40. A failed XCTL / LINK the program neither handles nor checks abends with the condition's code (NOTAUTH: AEY7); a planned LINK fault (#4648)
- **IBM.** EXEC CICS XCTL (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-xctl) and EXEC CICS LINK
  (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-link) list INVREQ, LENGERR, NOTAUTH and PGMIDERR (LINK adds
  ROLLEDBACK, SYSIDERR, TERMERR). A condition with no RESP / NOHANDLE and no HANDLE CONDITION for it takes CICS's default
  action: the task abends. The code of an unhandled NOTAUTH is AEY7 (https://www.ibm.com/docs/en/cics-ts/6.x?topic=codes-aey7).
  A failed XCTL transfers nothing and a failed LINK runs nothing: the issuing program continues, or abends.
- **What we do.** `resp.CONDITION_ABEND` gains NOTAUTH -> AEY7 (regenerated into `CicsSpec.java` and `ggcics_spec.h`, and the
  crucible runner's table). `CicsTask.link` and the stub's `GGCLINK` read a planned fault (`LINK <program> NTH RESP RESP2`) the
  way `xctl` / `GGCXCTL` do (#4049), so a scenario can fail a LINK on both sides.
- **Assumed / not modelled.** Which of NOTAUTH's RESP2 values (IBM lists 100 / 101 for resource security) a region gives is
  the scenario's to state; the runtimes carry whatever the plan names in the event. LINK's ROLLEDBACK / SYSIDERR / TERMERR are
  not raised by the region and have no entry in `CONDITION_ABEND`: refused by name in X43 (#4986).
- **Status:** ASSUMED; the abend code is the documented one, the planned fault is the harness's.

### X41. WEB RETRIEVE (CICS web support, the document of the last WEB SEND) — ASSUMED, REFUSED where IBM is silent (#4941, sibling of #4767)
- **WEB RETRIEVE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-retrieve). "Retrieves the DOCTOKEN for a CICS document
  that was sent with a WEB SEND command"; DOCTOKEN(data-area) "a buffer for the 16-byte binary token", the only option. The previous
  WEB SEND must use ACTION(EVENTUAL) (the Web domain then keeps a copy of the sent document's information); the document is the one
  sent, changes after the send are not in it; with two EVENTUAL sends the token is the second's. Conditions: INVREQ RESP2 1 "issued in a
  non-CICS Web support application", INVREQ RESP2 2 "no WEB SEND command has been issued", NOTFND RESP2 1 "the document is not
  available: the last WEB SEND specified DOCSTATUS(DOCDELETE), or was not a send of a document with ACTION(EVENTUAL)". WEB RETRIEVE
  is not valid after a client WEB SEND. The command is threadsafe.
- **What the runtimes do.** `CicsTask.webRetrieve` and the stub C `GGCWRTV` answer alike: no WEB SEND issued, INVREQ 2; the last WEB
  SEND an ACTION(IMMEDIATE) send, a FROM send or a DOCSTATUS(DOCDELETE) document send, NOTFND 1 (IBM lists each); the last WEB SEND an
  ACTION(EVENTUAL) (or ACTION-omitted: IBM's default, X37) document send that did not delete the document: NORMAL, the DOCTOKEN written.
  The area is written on NORMAL only.
- **What IBM leaves open, and what we do (REFUSED by name).** (1) INVREQ RESP2 1 (a task that is not CICS web support) cannot be told
  from a task whose request the run did not state, so an unstated request is refused (`the HTTP request is not stated`), as every
  X37 / X38 command. (2) Whether a WEB SEND that ended in a condition (INVREQ 11 / 72) "has been issued" is not stated: a WEB RETRIEVE after
  one (and before an accepted send) is refused. (3) The NORMAL outcome (#4941): IBM says the Web domain "keeps a copy"
  of the sent document's information and that changes made to the document after the send are not in what is retrieved, and does not say
  whether the token equals the DOCUMENT CREATE token. ASSUMED: it names a copy: a new document of the task (the next DOCUMENT token),
  holding the document as it was sent, created by the first WEB RETRIEVE of that send; later retrieves of the same send give the same token,
  a replacing EVENTUAL send starts again. A WEB SEND that replaced a held response is the "last WEB SEND". Whether a document sent with
  DOCDELETE can be retrieved is IBM's NOTFND 1 (named by IBM). The retrieve before the task ends is the only case: the send itself happens at
  the end of the task (X37). (4) The client form (a WEB SEND
  with SESSTOKEN) is not modelled at all (X35). (5) Every other option (IBM lists none) and a literal DOCTOKEN are refused when
  translating, in both translators.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven: `CicsTask` and the stub C answer one list of steps line
  for line over two request fixtures (tests/cics_crucible/test_cics_runtimes.py, `_X41_CASES` for NORMAL), both translators refuse every unmodelled option
  (tests/cobol_mainframe/test_det_translate.py, test_equivalence_cics.py). No estate program uses WEB RETRIEVE (det survey, the burned
  estates), so no port moves.

### X42. MOVE CONTAINER and the container browse (STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER) — ASSUMED, REFUSED where IBM is silent (#4951, sibling of #4884)
- **What IBM documents** (CICS TS 6.x, EXEC CICS MOVE CONTAINER (CHANNEL), STARTBROWSE CONTAINER (CHANNEL), GETNEXT CONTAINER
  (CHANNEL), ENDBROWSE CONTAINER (CHANNEL): https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-move-container-channel and its
  `startbrowse-` / `getnext-` / `endbrowse-container-channel` siblings). MOVE: CONTAINER names the source, AS the target ("If it
  already exists, its contents are overwritten"), CHANNEL the source's channel and TOCHANNEL the target's ("If the channel does not
  exist, CICS creates it"); each omitted means the current channel. CHANNELERR 1 (illegal TOCHANNEL name), 2 (CHANNEL not found),
  3 (read-only channel); CONTAINERERR 10 (source not found), 18 (illegal AS name); INVREQ 4 (CHANNEL or TOCHANNEL omitted, no
  current channel, outside a BTS activity), 30 / 31 (a CICS-defined read-only container as source / target). STARTBROWSE: CHANNEL
  ("must be either the current channel or a channel created by the program"; omitted with no current channel it "is treated as
  STARTBROWSE CONTAINER (BTS)"), BROWSETOKEN a fullword; CHANNELERR 2. "The order of returned containers is undefined and may
  change." GETNEXT: CONTAINER(data-area) "the 16-character name of the next data-container", BROWSETOKEN a fullword; END 2 (no more
  containers), ILLOGIC 1 (a current token, but not a container browse's), TOKENERR 3 (not valid: after the browse ended, after a
  sync point before it completed, or no STARTBROWSE). ENDBROWSE: ILLOGIC 1, TOKENERR 3. The unhandled conditions abend AEIU
  (ILLOGIC), AEXK (END) and AEZL (TOKENERR) (IBM's AEI/AEY/AEZ abend table; APAR PK43600 shows GETNEXT CONTAINER's TOKENERR as AEZL).
  Both sides model it: `ggcics.c` GGCMOVC / GGCSBRC / GGCGNXC / GGCEBRC and CicsTask moveContainer / startBrowseContainer /
  getNextContainer / endBrowseContainer; the spec entries are `standards/cics/commands/containers.py`.
- **Assumed.** (1) The browse returns the containers in the order they were created; IBM calls the order undefined, so a program
  that depends on it is outside what IBM promises, and the port and the stub agree on this one order. A container MOVEd to a new
  AS is created at that moment; an overwritten AS keeps its place. (2) Tokens are 1, 2, 3 ... in the order the task started
  browses (IBM only says "token"); a token is the issuing program's own: another program (a LINKed one) naming it gets TOKENERR 3
  (IBM: "meant only for the program that issued STARTBROWSE"); a SYNCPOINT (and a ROLLBACK) ends every browse. (3) After END, a
  further GETNEXT is END again; the token stays valid until ENDBROWSE. (4) The browse lists the names at STARTBROWSE; a GETNEXT
  after a container was added to or removed from the channel is refused (below), so no program here sees the unspecified middle
  ground; PUT over an existing container and a MOVE onto an existing AS change data, not names, and are allowed. (5) A MOVE that
  raises a condition changes nothing and creates no TOCHANNEL; the conditions are checked in the order INVREQ 4, CHANNELERR 2,
  CONTAINERERR 10 (IBM does not rank them). (6) The moved container keeps its data type (BIT / CHAR); the bytes are never
  converted, as for PUT / GET (X17). (7) GETNEXT's CONTAINER area takes the 16-character name, blank-padded; a shorter program area
  takes its first bytes.
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run time): any
  option IBM's command does not list; MOVE CONTAINER onto itself (the same name in the same channel: IBM does not say); MOVE onto an
  existing container of the other data type (its type, or an INVREQ, is not documented; the same open question PUT has, X17);
  GETNEXT after the browsed channel gained or lost a container (IBM says nothing of changes during a browse); STARTBROWSE with no
  CHANNEL and no current channel (IBM: the BTS form, not modelled); a channel an XCTL left behind and a blank / embedded-blank name
  (X17's refusals). **Unreachable, so no outcome:** CHANNELERR 1 and CONTAINERERR 18 (the names' illegal-character rules are not
  modelled: such a name is refused, X17), CHANNELERR 3 and INVREQ 30 / 31 (no channel or container is read-only: CICS-defined
  containers are not modelled), ILLOGIC 1 (no other browse hands out a token: WEB browses and INQUIRE URIMAP's have none).
- **Reached.** Unit proofs: `tests/cics_crucible/test_cics_runtimes.py` runs one 31-step scenario (MOVE across, within and to a new
  channel, onto an existing container, every condition; browse to END, ENDBROWSE, a reused token, a never-given token, a sync point,
  another program's token) on the stub and on CicsTask, which print the same lines, and the refusals above on both. No cics-crucible
  case yet: a hand-traced case is a companion PR on the crucible.

### X43. LINK conditions ROLLEDBACK, SYSIDERR, TERMERR: refused by name; EIBRESP2 after a failed XCTL / LINK is the event's (#4986, sibling of #4648)
- **IBM.** EXEC CICS LINK conditions (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-link) list INVREQ, LENGERR, NOTAUTH,
  PGMIDERR, and also ROLLEDBACK, SYSIDERR and TERMERR (the conditions of a LINK to a program in another region, or one whose
  unit of work rolled back). XCTL has none of those three. IBM gives each an unhandled-condition abend code in its own abend
  page; those codes are not sourced here, and are not guessed.
- **What we do.** Nothing models them: `CicsTask.link` and the stub's `GGCLINK` never raise them, `resp.CONDITION_ABEND` has no
  entry for them, and `equivalence_cics.fault_lines` refuses a LINK plan naming one (`LINK_REFUSED_CONDITIONS`), whatever its
  RESP2 and NTH. SYSIDERR stays plannable for START and CANCEL, whose IBM conditions list it.
- **EIBRESP2 after a failed XCTL / LINK (done).** `CicsTask.transferResp2()` is the RESP2 of the program's last LINK / XCTL as its
  event carries it, so a planned fault's RESP2 reaches EIBRESP2 as it does in the GnuCOBOL stub. It replaces `DetCics.xctlResp2`
  / `linkResp2`, which mapped the condition name only (LENGERR 11, PGMIDERR 1, else 0).
- **Refused.** A program that LINKs and branches on ROLLEDBACK, SYSIDERR or TERMERR is not proven here; the owner rule is that a
  program is not proven while a program it LINKs has holes. When IBM's abend pages are sourced, add them to `CONDITION_ABEND`,
  model the condition, and remove the refusal.
- **Status:** REFUSED for the three conditions; the RESP2 fix is exact.

### X44. DELETE CHANNEL and QUERY CHANNEL — ASSUMED, REFUSED where IBM is silent (#5005, sibling of #4951)
- **What IBM documents** (CICS TS 6.x, EXEC CICS DELETE CHANNEL and EXEC CICS QUERY CHANNEL:
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-delete-channel and `summary-query-channel`). DELETE CHANNEL(name): the
  channel (1 - 16 characters) is deleted, and "deleting the channel also deletes every container it holds". Its only condition is
  CHANNELERR, with RESP2 2 (the channel could not be found), 3 (a read-only channel), 4 (the current channel), 5 (the transaction
  channel) and 6 (a channel not owned by the calling program). QUERY CHANNEL: CHANNEL(name) is required; CONTAINERCNT(data-area)
  "returns, as a fullword binary value, a count of the number of containers that are in the specified channel"; its only condition is
  CHANNELERR RESP2 2 (the channel could not be found). CHANNELERR abends AEZV when unhandled (X17). Both sides model it: `ggcics.c`
  GGCDELH / GGCQCHN and CicsTask deleteChannel / queryChannel; the spec entries are `standards/cics/commands/containers.py`.
- **Assumed.** (1) A channel is found in the program's scope (X17): the channels it created and the one it was passed; a channel in
  another program's scope is not found (CHANNELERR 2), so a LINKed program deleting or querying a channel its caller made but did
  not pass gets CHANNELERR 2. (2) After a DELETE the channel is gone from the scope: a later GET / DELETE CONTAINER, QUERY or DELETE
  CHANNEL naming it is CHANNELERR 2, and a PUT CONTAINER naming it makes a new, empty channel ("If the channel does not exist, it is
  created", X17) that holds none of the old containers. (3) A channel emptied container by container still exists: QUERY CHANNEL
  gives CONTAINERCNT 0, and DELETE CHANNEL succeeds. (4) CONTAINERCNT is set on NORMAL only; IBM does not say what it holds on
  CHANNELERR (as FLENGTH, X17). (5) A browse (X42) of a channel that was then deleted is refused at its next GETNEXT, like any change to
  the browsed channel.
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run time): any option
  IBM's commands do not list; a missing CHANNEL (or, for QUERY, CONTAINERCNT); DELETE CHANNEL of the program's current channel (IBM's
  RESP2 4 names the current channel, 5 the transaction channel and 6 a channel the program does not own, and a channel a program is
  passed is the current one, is not its own, and for the task's first program is also the transaction channel: IBM ranks none, so
  the port refuses instead of choosing); a channel an XCTL left behind and a blank / embedded-blank name (X17's refusals).
  **Unreachable, so no outcome:** CHANNELERR 3 (no channel is read-only: CICS-defined channels are not modelled); 4, 5 and 6 as
  separate outcomes (the refusal above covers every case they could apply to).
- **INQUIRE CONTAINER** stays refused whole, in every option set (#5005 asked for "the browse form"; there is none to model).
  IBM's INQUIRE CONTAINER page (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-inquire-container, read 2026-10-13) has one
  syntax: `INQUIRE CONTAINER(data-value) ACTIVITYID / PROCESS / PROCESSTYPE / DATALENGTH(data-area) / SET(data-area)`, a BTS
  data-container inquiry, with ACTIVITYERR (2, 3, 29, 30), PROCESSERR (2, 4, 13, 33), CONTAINERERR 1, IOERR 30 and NOTAUTH 101. It has
  no CHANNEL, BROWSETOKEN or START / NEXT / END form. A channel's container names are STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER
  (X42, modelled) and a container's length is `GET CONTAINER ... NODATA FLENGTH` (X17). BTS is out of scope, so the whole command,
  channel-shaped or BTS-shaped, is refused by name with that reason (`api.py`; `tests/core_engine/test_cics_spec.py`
  `test_inquire_container_is_refused_whole_in_every_form`, `tests/cobol_mainframe/test_det_translate.py`
  `test_inquire_container_is_refused_by_name_whatever_its_options`). Nothing was turned from REFUSED to ASSUMED.
- **Reached.** The hand-traced case `ca-channel-browse` (cics-crucible, `commarea-mismatch`, scenarios `browse-move-delete` and
  `unhandled-channelerr`: QUERY CHANNEL, the browse, MOVE, DELETE CHANNEL, CHANNELERR 2 / CONTAINERERR 10 / TOKENERR 3 / END 2, AEZV)
  was written from IBM's pages, not from our output, and avoids the browse order, CONTAINERCNT on a condition and a GETNEXT after
  END. Run `--unpinned` against the companion PR's checkout, the cobol-stub side passes both scenarios; the java sides fail as
  `ca-channel-containers`' do today (no port of the programs; the Java recorded no event). The pin is not bumped here, so
  `tests/cics_crucible/baseline.json` is unchanged. Unit proofs: `tests/cics_crucible/test_cics_runtimes.py` runs one 24-step scenario (counts, delete, the channel gone
  and recreated, an emptied channel, a LINKed program's scope, every condition) on the stub and on CicsTask, which print the same
  lines, and the refusals above on both; the translators' tests are in `tests/cobol_mainframe/test_det_translate.py` and
  `test_equivalence_cics.py`.

### X45. DEFINE / QUERY / DELETE DCOUNTER with MINIMUM and MAXIMUM; GET DCOUNTER INCREMENT [WRAP] at the limits — ASSUMED, REFUSED where IBM is silent (#4770)
- **What IBM says** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-define-counter-define-dcounter, ...summary-get-counter-get-dcounter,
  ...summary-query-counter-query-dcounter, ...summary-delete-counter-delete-dcounter). DEFINE DCOUNTER: VALUE, MINIMUM and MAXIMUM are
  "a doubleword unsigned value for DCOUNTER"; "If you omit the MINIMUM parameter, the named counter is defined with a default minimum
  of low-values", MAXIMUM "a doubleword filled with X'FF'"; "If you specify the MINIMUM parameter, you must also specify a VALUE";
  VALUE "equal to, or greater than, the minimum value, up to the maximum value plus 1"; INVREQ RESP2 406 "VALUE is invalid", 407 "MINIMUM
  or MAXIMUM is invalid" (MAXIMUM below MINIMUM). "The named counter server stores all values as doubleword unsigned values."
  GET: VALUE "the current number"; the counter is incremented after the number is assigned; at its limit, with neither REDUCE
  nor WRAP, SUPPRESSED (72) RESP2 101 and "the current number is not changed"; WRAP "resets the current value of the named counter
  equal to the minimum value defined for the counter"; INVREQ 406 "INCREMENT exceeds the counter's total range". QUERY DCOUNTER:
  VALUE, MINIMUM and MAXIMUM data areas, "a doubleword unsigned binary value".
- **Modelled** (`CicsTask.defineDcounter` / `queryDcounter` / `getCounter(pool, name, increment, wrap)`, the stub's `GGCDDCN` /
  `GGCQDCN` / `GGCGDCN` on `counters.cfg`, whose rows gain `MINIMUM MAXIMUM` after the value; the det translator and
  `equivalence_cics.py`): a counter DEFINE DCOUNTER made holds its limits as unsigned doublewords (one store for both forms, as X30).
  A GET hands out the value and adds INCREMENT; a counter at MAXIMUM + 1 (the value past MAXIMUM, where an earlier GET left it) is
  SUPPRESSED 101 and unchanged, or with WRAP the GET returns MINIMUM and the counter is MINIMUM + INCREMENT. 407 is checked before 406,
  then 202 (403 / 404 first: the page gives no order). DELETE DCOUNTER is DELETE COUNTER's call. GET DCOUNTER's VALUE is written
  unsigned (a value past 2**63 is not negative); INCREMENT is read as 64 bits (a COBOL `.intValue()` truncated it before).
- **What IBM leaves open, and what we do.** (1) What WRAP does when the increment overshoots (a counter below MAXIMUM whose INCREMENT
  carries it past MAXIMUM + 1) and where REDUCE's boundary lies: REFUSED ("GET COUNTER with an INCREMENT past MAXIMUM + 1"); WRAP acts
  only at a counter already at MAXIMUM + 1. (2) The 406 boundary of INCREMENT ("exceeds the counter's total range"): an INCREMENT
  beyond MAXIMUM - MINIMUM is REFUSED, one within it is not an error. (3) A counter whose maximum is a doubleword of X'FF' has
  no MAXIMUM + 1 in a doubleword: it is never at its limit, and one that would pass it is REFUSED ("GET COUNTER past a doubleword").
  (4) A counter DEFINE COUNTER made, or a scenario states, has no limits entry: the run does not state them, so GET behaves as before
  (WRAP changes nothing; past 4294967295 REFUSED) and QUERY DCOUNTER MINIMUM / MAXIMUM of it is REFUSED -- IBM states the fullword
  form's default maximum, X'7FFFFFFF', but its signed reading of low-values is the open point X30 left, so the fullword form's
  MINIMUM / MAXIMUM stay refused. (5) A COUNTER and a DCOUNTER of one name are one counter (ASSUMED, X30): IBM says to "access a
  counter with the same command set that defined it" and states nothing for a mismatch. (6) The order of 407 / 406 / 202 (above).
  (7) VALUE / MINIMUM / MAXIMUM are data areas in the stub translator (a literal is refused); the det translator takes literals too.
- **Since #5039:** DEFINE COUNTER's MINIMUM / MAXIMUM are X50's, GET's REDUCE / COMPAREMIN / COMPAREMAX and NOSUSPEND are X53's.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven on both runtimes scenario for scenario
  (tests/cics_crucible/test_cics_runtimes.py `_X45_CASES`) and both translators; no case runs it yet (zECS ZECSNC is assembler, its
  DEFINE DCOUNTER / ZECS001's GET DCOUNTER are not in a COBOL case the corpus ships whole).

### X46. FORMATTIME day-of-year and binary forms, DUMP TRANSACTION — ASSUMED, REFUSED where IBM is silent (#4415 slice 3)
- **FORMATTIME date forms** (CICS TS 6.x, EXEC CICS FORMATTIME, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-formattime).
  YYDDD "the 6-character user field where CICS returns the date, in year/day format; for example, 95/301", YYYYDDD "8-character
  ... for example 1995/200", YYDDMM "8-character ... year/day/month format; for example, 95/30/10", YYYYDDMM 10-character.
  "If no separator is requested, the returned value is left-aligned" in the field. The page's day-of-year has three digits only
  by its examples (95/301, 1995/200) and the 6- / 8-character field widths: **ASSUMED** three digits with leading zeros (day 1
  is `001`). DATESEP applies as for the other forms (no DATESEP: none; DATESEP alone: '/'). The same INVREQ RESP2 1 for an
  ABSTIME below zero as X28.
- **FORMATTIME binary forms.** DAYCOUNT "the number of days since 1 January 1900 (day 1), as a fullword binary number":
  **ASSUMED** read as 1 January 1900 being day 1 (ABSTIME 0 gives 1). DAYOFMONTH, MONTHOFYEAR (January=1), YEAR (the full four
  figures) "as a fullword binary number"; DAYOFWEEK "Sunday=0, Saturday=6" (1 January 1900 was a Monday: 1). MILLISECONDS "the
  number of milliseconds in the current second specified by ABSTIME, as a binary integer in the range 0 - 999": the page does
  not say fullword or halfword, so the value is **written by the receiving area's declared usage** (a field too small for the
  value is the program's own size error, as for any store) rather than a width being chosen. Local time, as the other forms:
  IBM says the date and time values other than DATESTRING "are returned in local time" and ABSTIME is the region's clock.
- **Refused by name:** DATE, FULLDATE and DATEFORM return the date "in the format specified in the DATFORM system
  initialization parameter" (DATEFORM: YYMMDD, DDMMYY or MMDDYY): the run states no DATFORM. DATESTRING (RFC1123 / RFC3339,
  with STRINGFORMAT, and STRINGZONE UTC / LOCAL) needs the region's offset from UTC, which the run does not state; INVREQ RESP2 2
  (an invalid STRINGFORMAT CVDA) therefore does not arise.
- **DUMP TRANSACTION** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-dump-transaction), also the bare `EXEC CICS DUMP`
  an old program writes (the page does not say they are one command, so the bare form is refused on its own). IBM lists INVREQ
  RESP2 13 (a DUMPCODE with unprintable, leading or embedded blank characters: the dump is still taken), IOERR 9 / 10 / 13,
  NOSPACE 4, NOSTG 5, NOTOPEN 6, OPENERR 7 and SUPPRESSED 1 / 2 / 3 (the dump table's MAXIMUM, its NOTRANDUMP, a user exit);
  DUMPID returns "xxxx/yyyy" with a run number; "if the DUMPCODE has a SYSDUMP entry in the transaction dump table, a system
  dump is also taken". Every outcome but the DUMPCODE's validity is the region's dump setup (dump table, dump data set, user
  exit, run count), none of which a run states, and the page does not say the task continues after a successful dump. Not
  modelled; refused by name, with its options.
- **QUERY** (#4415 lists it): QUERY COUNTER is X29 (QUERY DCOUNTER is #4770, QUERY CHANNEL #5005); QUERY SECURITY stays refused
  (the region has no security manager).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent.

### X47. The pointer lane: GETMAIN / FREEMAIN, WEB RECEIVE SET and SET ADDRESS OF — ASSUMED, REFUSED where IBM is silent (#4771, zECS)
- **GETMAIN** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-getmain). SET(ptr-ref) is "the address of the first byte of the
  acquired storage", "If a zero or negative FLENGTH or LENGTH causes LENGERR, ptr-ref is set to zero". FLENGTH is a fullword; LENGTH is "kept
  only for compatibility", a halfword "limited to 65520 bytes", zero is LENGERR. INITIMG(data-value): "CICS sets every byte of the storage to
  that value"; "There is no default initialization", so without INITIMG the contents are undefined. LENGERR RESP2 1 (FLENGTH below 1, LENGTH
  zero); NOSTG RESP2 2 (the request exceeds the storage available). Task storage is released at task end; SHARED storage outlives it.
- **FREEMAIN** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-freemain). DATAPOINTER(ptr-value) "takes the pointer returned by
  GETMAIN SET"; the length released is the GETMAIN length. INVREQ RESP2 1: the storage was not acquired by GETMAIN. IBM does not say what a
  second FREEMAIN of the same address returns.
- **WEB RECEIVE SET** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-receive-server). SET "sets [the pointer] to the address of
  the received data", "valid until the next receive command or the end of task"; LENGTH "must be specified when SET (or INTO) is used" and holds
  the amount returned; MAXLENGTH "is optional" with SET ("receives all the remaining data"), zero or below LENGERR RESP2 16, a longer body cut
  with LENGERR RESP2 57 (NOTRUNCATE is refused, X38). IBM does not say who owns the storage, nor whether FREEMAIN is allowed on it.
- **What the runtimes do.** One shape in both, `CicsTask` (`getmain`, `freemain`, `acquireReceived`, `addressOf`, `storageAt`) with `DetCics`
  (`getmain`, `receivedBlock`, `setAddress`, `setAddressOfRecord`, `setPointerToRecord`) in the port, `GGCGETM` / `GGCFREM` / `GGCWRCS` in the stub.
  In the port a POINTER holds an 8-byte handle (0 is NULL) of a block the task owns; SET ADDRESS OF record TO ptr makes the record's `Storage`
  the block's byte array, so a write through the record or through another record set to the same block is seen by both (the stub's are real
  addresses and GnuCOBOL's own SET ADDRESS OF). A handle is never a number the program can compute with.
- **Assumed.** (1) GETMAIN's placement and key options (BELOW, USERDATAKEY, CICSDATAKEY, EXECUTABLE) change no byte the program sees, so they
  are accepted and ignored. (2) A LINKAGE record longer than the block it is set to reads zero bytes past the block in the port (IBM: bytes
  that are not the program's; GnuCOBOL: whatever the heap holds), so a program must not read past the storage it addressed: ZECS001's
  CACHE-MESSAGE is 32000 bytes over a body or a GETMAIN of any size. (3) WEB RECEIVE SET with MAXLENGTH not above zero: LENGERR RESP2 16 and the
  pointer unchanged (IBM does not say). (4) A pointer holds a handle, not an address, so a pointer written to a COMMAREA, or read as a number,
  is refused (the existing "a POINTER that is not NULL in a COMMAREA is not modelled", C9).
- **Refused by name.** At translation: GETMAIN without SET, without exactly one of FLENGTH / LENGTH, without INITIMG (IBM gives no default
  contents) or with a literal INITIMG (IBM: "In COBOL, use a data area"); SHARED (outlives the task), NOSUSPEND (NOSTG is not modelled), FREEMAIN
  DATA(area), GETMAIN64 / FREEMAIN64; a pointer that is not a plain USAGE POINTER (a table element, a subscripted or qualified name) or that a
  REDEFINES overlays (ZECS001's CACHE-ADDRESS-X, `ADD n TO` the address: pointer arithmetic); SET ADDRESS OF / ADDRESS OF a record that is not a
  LINKAGE 01 (a WORKING-STORAGE record shares its section's storage; a subordinate item such as ZECS001's ZF-DATA has no storage of its own);
  SET ADDRESS OF ... TO NULL. At run time: a length above 256 MiB (IBM's NOSTG is the region's DSALIMIT, not stated) or a LENGTH above 65520; a
  second FREEMAIN of a block (IBM does not say); FREEMAIN of a WEB RECEIVE SET body (IBM does not say whether it is allowed); SET ADDRESS OF a
  null or unknown pointer, or freed storage; a record longer than storage that another record already addresses.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven only (see `reached`): both runtimes answer 24 step lists alike, the
  translator's shape and every refusal are tested in tests/cobol_mainframe/test_det_translate.py and test_equivalence_cics.py, and a whole program
  with the four statements translates with no hole and runs (tests/cobol_mainframe/test_pointer_lane_4771.py). No cics-crucible case or estate
  program exercises it yet, so no port moves and no ZECS program is made whole by this entry.

### X48. Injected duplicate-key file faults: DUPKEY delivers the record, each condition only on the commands IBM lists it for — ASSUMED, REFUSED where IBM is silent (#4623)
- **DUPKEY** (CICS TS 6.x, READ / READNEXT / READPREV "Conditions": DUPKEY, RESP2 140): "a record is retrieved through an
  alternate index that has the NONUNIQUEKEY attribute, and another alternate index record with the same key follows". The
  condition qualifies a successful read: IBM retrieves the record. The injection therefore runs the read and turns its
  NORMAL into DUPKEY / 140 (the record moved INTO, a browse's RIDFLD set, a READ UPDATE held, as for NORMAL). A read that finds
  no record (NOTFND, ENDFILE, LENGERR) has no DUPKEY to give: the fault does not fire (and so the run's fault log does not
  hold it, which the harness reports). **ASSUMED:** the DUPKEY read's own RIDFLD / INTO are as NORMAL's (the pages say the
  record is retrieved and do not say otherwise). The harness has no alternate index: the fault is planned, not derived from
  duplicate keys in a path.
- **DUPREC** (WRITE: RESP2 150 "adding a record whose key already exists", also a UNIQUEKEY alternate key already present;
  REWRITE: RESP2 150, the alternate key already in the upgrade set). The write / rewrite does nothing.
  A unique-alternate-key violation on WRITE is DUPREC 150, **not** DUPKEY: the WRITE page lists no DUPKEY.
- **Refused by name:** DUPKEY on any other command (WRITE, REWRITE, STARTBR, ENDBR: not in their lists), DUPREC on any command
  but WRITE / REWRITE, and an explicit RESP2 that is not IBM's. **DUPKEY on DELETE:** the DELETE page lists it (RESP2 140) but
  does not say whether the record is deleted, so the outcome is not modelled and the fault is refused.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent.

### X49. Injected file faults: each condition only on the file commands IBM lists it for, with IBM's RESP2 — ASSUMED, REFUSED where IBM is silent (#5044, sibling of #4623)
- **Source.** CICS TS 6.x, the "Conditions" of each command's page
  (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-read, and `summary-readnext`, `-readprev`, `-write`, `-rewrite`,
  `-delete`, `-startbr`, `-endbr`; UNLOCK is not a plannable command, see below). The condition list (the syntax line's
  `Conditions:`) and each RESP2 were read from the raw page text on 2026-10-13, not from a summary.
- **Per command.** FILENOTFOUND 1, NOTAUTH 101, IOERR 120, SYSIDERR 130 and ISCINVREQ 70: all eight. ILLOGIC 110: READ, STARTBR,
  ENDBR, WRITE, DELETE. NOTFND 80: READ, READNEXT, READPREV, STARTBR, DELETE. ENDFILE 90: READNEXT, READPREV. DISABLED 50 and
  NOTOPEN 60: READ, WRITE, DELETE, STARTBR. NOSPACE 100: WRITE, REWRITE. LOCKED 106: READ, READNEXT, READPREV, WRITE, REWRITE,
  DELETE. LENGERR 10 / 11 / 13: the three reads; 10 / 12 / 14: WRITE, REWRITE. INVREQ: READ 20 25 26 28 42; READNEXT 20 25 26 34
  37 42; READPREV 20 24 26 37 41; STARTBR 20 25 26 33 42; ENDBR 35; WRITE 20 23 26; REWRITE 30 47; DELETE 20 21 22 25 26 31 42 47.
  DUPKEY / DUPREC as X48.
- **REWRITE lists no NOTOPEN and no DISABLED** (the page's syntax line and its Conditions section both lack them; the worker's
  doubt in #5044 was checked against the raw text). They are refused on REWRITE by name. READNEXT, READPREV and ENDBR list neither
  either. carddemo-userupd's `rewrite-not-open` therefore became `rewrite-io-error` (IOERR is listed;
  the program's WHEN OTHER branch is the same).
- **Injections.** A planned condition is what the program sees, not something the region raises: SYSIDERR / ISCINVREQ (a remote
  file's answers) are planned like IOERR, as cbsa-inqcust's retry scenarios do. RESP2 131 / 132 (coupling-facility data tables)
  are not planned.
- **Refused by name.** LOADING 104, CHANGED 109, SUPPRESSED 105 (data tables) and RECORDBUSY 107 (NOSUSPEND, RLS only); READ's
  NOSPACE 100 (IBM: an RLS file READ after a WRITE got it) and the RLS / BDAM / user-maintained and coupling-facility data-table /
  XRBA values of INVREQ, NOTFND and NOSPACE; NOTFND 80 on REWRITE (IBM: user-maintained and CF data tables only); ILLOGIC on
  READNEXT / READPREV / REWRITE (IBM adds "the browse in progress is terminated"; neither runtime ends a browse on an injected
  fault). DUPKEY on DELETE stays refused (X48): the DELETE page restates it and still does not say whether the record is deleted.
- **Not covered here.** UNLOCK (not a plannable command in the stub or CicsTask). A planned IOERR, NOSPACE, NOTOPEN, DISABLED,
  FILENOTFOUND or LOCKED has no entry in `CONDITION_ABEND`, so a program that neither checks RESP nor handles the condition is
  abended by neither runtime with IBM's code (LOCKED: AEX8 is documented on the pages); every case plans these where the program
  checks RESP.
- **Status:** ASSUMED where listed (the planned RESP2 is IBM's, the effect is the program's), REFUSED where IBM is silent or the
  runtimes do not model it.

### X50. DEFINE / QUERY COUNTER with MINIMUM and MAXIMUM; GET COUNTER INCREMENT [WRAP] at the limits — ASSUMED, REFUSED where IBM is silent (#5039)
- **What IBM says** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-define-counter-define-dcounter, ...summary-get-counter-get-dcounter,
  ...summary-query-counter-query-dcounter, ...summary-delete-counter-delete-dcounter). DEFINE COUNTER: VALUE, MINIMUM and MAXIMUM are
  "a fullword binary value for COUNTER"; "If you omit the MINIMUM parameter, the named counter is defined with a default minimum
  of low-values", MAXIMUM "a fullword of high-values (X'7FFFFFFF') for COUNTER"; "If you specify the MINIMUM parameter, you must also specify a VALUE";
  VALUE "equal to, or greater than, the minimum value, up to the maximum value plus 1"; INVREQ RESP2 406 "VALUE is invalid", 407 "MINIMUM
  or MAXIMUM is invalid" (MAXIMUM below MINIMUM, or outside the range for the counter type). "The named counter server stores all values as doubleword unsigned values."
  GET: VALUE "the current number"; the counter is incremented after the number is assigned; at its limit, with neither REDUCE
  nor WRAP, SUPPRESSED (72) RESP2 101 and "the current number is not changed"; WRAP "resets the current value of the named counter
  equal to the minimum value defined for the counter"; INVREQ 406 "INCREMENT exceeds the counter's total range". QUERY COUNTER:
  VALUE, MINIMUM and MAXIMUM data areas, fullword binary values.
- **Modelled** (`CicsTask.defineCounter` / `queryCounter` / `getCounter(pool, name, increment, wrap)`, the stub's `GGCDCNT` /
  `GGCQCNT` / `GGCGCNT` on `counters.cfg`, whose rows hold `MINIMUM MAXIMUM` after the value; the det translator and
  `equivalence_cics.py`): a counter DEFINE COUNTER made holds its limits as fullwords (stored alongside doubleword counters in one store, as X30 / X45).
  A GET hands out the value and adds INCREMENT; a counter at MAXIMUM + 1 (the value past MAXIMUM, where an earlier GET left it) is
  SUPPRESSED 101 and unchanged, or with WRAP the GET returns MINIMUM and the counter is MINIMUM + INCREMENT. 407 is checked before 406,
  then 202 (403 / 404 first: the page gives no order).
- **What IBM leaves open, and what we do.** (1) What WRAP does when the increment overshoots (a counter below MAXIMUM whose INCREMENT
  carries it past MAXIMUM + 1) and where REDUCE's boundary lies: REFUSED ("GET COUNTER with an INCREMENT past MAXIMUM + 1"); WRAP acts
  only at a counter already at MAXIMUM + 1. (2) The 406 boundary of INCREMENT ("exceeds the counter's total range"): an INCREMENT
  beyond MAXIMUM - MINIMUM is REFUSED, one within it is not an error. (3) The signed reading of low-values and negative values (the open point X30 left):
  a VALUE or MINIMUM below zero is REFUSED ("DEFINE COUNTER with a VALUE below zero"). (4) A counter a scenario states has no limits entry:
  QUERY COUNTER MINIMUM / MAXIMUM of it is REFUSED ("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state").
  (5) A COUNTER and a DCOUNTER of one name are one counter (ASSUMED, X30 / X45). (6) The order of 407 / 406 / 202 (above).
  (7) VALUE / MINIMUM / MAXIMUM of DEFINE COUNTER may be decimal literals in both translators (the stub translator stages one big-endian in GG-FLAGS); QUERY COUNTER writes them, so the stub translator takes data areas only.
- **Since #5039 (X53):** REWIND, UPDATE, GET's REDUCE / COMPAREMIN / COMPAREMAX and NOSUSPEND are modelled or refused by name in X53.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven on both runtimes scenario for scenario
  (tests/cics_crucible/test_cics_runtimes.py `_X50_CASES`) and both translators.

### X51. A RETURN or XCTL COMMAREA passes LENGTH bytes, a LINK's is passed by address — the det port cuts the bytes it passes beside the DTO at LENGTH (#4817, #4695)
- **What.** The det port keeps the bytes of a COMMAREA beside its DTO so a numeric DISPLAY field holding spaces, or a byte no DTO
  decodes, reaches the next task as it was (#4806 XCTL / LINK, #4817 RETURN TRANSID). Those bytes are the record's whole span;
  the command's LENGTH can be shorter.
- **IBM.** EXEC CICS RETURN (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-return) and EXEC CICS XCTL
  (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-xctl): COMMAREA names the data area passed on and LENGTH its length;
  the receiving program's EIBCALEN is that length, so what it may address is LENGTH bytes. The pages say nothing of the bytes
  of a longer record past LENGTH: a program must not read them (the entry treats the cut as the model, ASSUMED, not as IBM text).
- **What we do.** `CicsTask.returnTransid` / `returnImmediate` / `xctl` keep `min(LENGTH, bytes)` of the bytes passed (a copy); a
  null LENGTH keeps all of them. A LINK passes its area by address (#4806), so the callee's storage is the caller's, tail included:
  not cut. A RETURN whose LENGTH is past the DTO passes the COMMAREA as a `byte[]` in the region's EBCDIC (#4679): the facade's
  `handleTransaction` answers it as an `Object` (it has no DTO type for it), `returned(Dto.class)` refuses it by name, and
  `returnedBytes()` is null (the bytes are the answer itself) (#4695).
- **Status:** ASSUMED. The oracle's (GnuCOBOL) storage past the LENGTH of a copied COMMAREA is not IBM's either; no program may rely on it.

### X52. File update TOKEN: READ UPDATE TOKEN / REWRITE TOKEN / DELETE TOKEN / UNLOCK TOKEN — ASSUMED, REFUSED where IBM is silent (#5078)
- **What IBM documents** (CICS TS 6.x, EXEC CICS READ, REWRITE, DELETE, UNLOCK:
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-read, `summary-rewrite`, `summary-delete`, `summary-unlock`). READ TOKEN(data-area):
  "a unique identifier for this READ UPDATE request ... for use in associating a subsequent REWRITE or DELETE (or UNLOCK) request with the
  record returned on this READ UPDATE request"; "If you specify TOKEN it implies update". REWRITE and UNLOCK TOKEN: "a unique request
  identifier ... used to associate it with a previous READ, READNEXT, or READPREV command that specified UPDATE"; DELETE TOKEN: "the value
  to use is the value returned in the TOKEN held by the earlier READ UPDATE ... request". INVREQ RESP2 47 on all three: "a token whose value
  cannot be matched against any token in use for an existing read for UPDATE". A tokenless REWRITE with no tokenless READ UPDATE before it is
  INVREQ RESP2 30, a tokenless DELETE without RIDFLD INVREQ RESP2 31, a second tokenless READ UPDATE on the file without an intervening
  REWRITE, DELETE, UNLOCK or SYNCPOINT INVREQ RESP2 28 (#5092: all three modelled, in both runtimes; a record held under a TOKEN is not the file's
  tokenless hold, so it neither raises 28 nor answers a tokenless REWRITE or DELETE). Both sides model it: `ggcics.c` GGCREAD / GGCREWR / GGCDELT / GGCUNLK and CicsTask holdToken / rewriteToken /
  deleteToken / unlockToken; the spec entries are `standards/cics/commands/files.py`.
- **Assumed.** (1) The token's value: IBM calls it "a unique identifier" and says nothing of its value, so the runtimes issue the task's
  1, 2, 3, ... (never 0); a program that displays or computes on the token sees that value, not the one z/OS gives. (2) Several records can be
  held at once, on one file or on several, each under its own token (IBM's point of TOKEN); the file's tokenless hold is separate: a tokenless
  REWRITE or DELETE does not act on a record held under a token (INVREQ), and a REWRITE / DELETE TOKEN does not act on the tokenless hold.
  (3) A token is spent by the REWRITE, DELETE or UNLOCK that uses it; using it again, or a token of another file's record, is INVREQ RESP2 47
  (IBM lists 47 for a value that "cannot be matched against any token in use"; another file's token is such a value here). (4) A SYNCPOINT
  (and a ROLLBACK) ends every hold and every token. (5) A READ UPDATE TOKEN that is not NORMAL (NOTFND ...) issues no token and leaves the
  program's field as it was. (6) UPDATE is implied by TOKEN, so READ TOKEN alone holds the record.
- **Still unsaid (#5092).** A tokenless REWRITE whose FROM has another key than the held record's: the stub answers INVREQ RESP2 0, CicsTask
  ignores the key; IBM states no RESP2 for it. A READ UPDATE's 28 is checked before a planned fault is consumed.
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run time): READNEXT and READPREV
  UPDATE [TOKEN] (IBM allows a browse for update only on files accessed in RLS mode, which the region has none of); DELETE with TOKEN and
  RIDFLD (IBM does not say which record goes) or GENERIC; a REWRITE TOKEN whose FROM has another key than the held record's; READ UPDATE TOKEN
  with LENGTH shorter than the record (LENGERR: whether the record is then held is unsaid, as X6); more than 64 records held under tokens at once (the stub's table).
- **UNLOCK without TOKEN (#5079).** IBM (EXEC CICS UNLOCK) releases the exclusive control a READ UPDATE took on the file's record. Both runtimes
  release the file's tokenless hold (CicsTask.unlockHeld, ggcics.c GGCUNLK without TOKEN); a hold under a token is separate (use UNLOCK TOKEN).
  IBM (cics-ts 6.x, summary-unlock): "If an UNLOCK command does not have a token, an attempt is made to match it to either a read with the
  UPDATE option that also does not have a token, or to a WRITE MASSINSERT operation. If neither of these is found, no action is taken and a
  NORMAL response is returned." So with nothing held (never read for update, already released, ended by a SYNCPOINT, NOTFND read) it is
  NORMAL, RESP2 0. Refused by name: the WRITE MASSINSERT match (WRITE MASSINSERT is not an option of the modelled WRITE).

### X53. REWIND / UPDATE COUNTER and DCOUNTER, GET REDUCE / COMPAREMIN / COMPAREMAX, NOSUSPEND on the named-counter commands — ASSUMED, REFUSED where IBM is silent (#5039)
- **What IBM says** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-rewind-counter-rewind-dcounter,
  ...summary-update-counter-update-dcounter, ...summary-get-counter-get-dcounter). REWIND: "resets a named counter that has reached its
  limit" to its defined minimum; INCREMENT is "used to check whether the counter can be reset ... the server applies it before testing the
  counter-at-limit condition"; SUPPRESSED RESP2 102 "the counter hasn't reached its limit, even after applying any specified increment";
  INVREQ 406 "the INCREMENT value exceeds the counter's total range ((maximum - minimum) + 1)". UPDATE: VALUE "the new number to set as the
  current value"; INVREQ 406 "the VALUE is invalid. It is below the minimum, or above the maximum plus 1"; SUPPRESSED RESP2 103 "the current
  value of the named counter is not within the range specified by the COMPAREMAX and COMPAREMIN parameters". GET: REDUCE "the server may
  reduce the increment, and the request succeeds with the current value set to the maximum plus 1"; COMPAREMIN "returns the current value
  if it is equal to or greater than this value", COMPAREMAX "less than or equal"; "when COMPAREMAX is less than COMPAREMIN, the value is
  in range if it satisfies either comparison"; SUPPRESSED RESP2 103 for a value outside the range. NOSUSPEND (all six commands): without
  it a request "retries until success" during a coupling-facility structure rebuild; with it BUSY (128) RESP2 500.
- **Modelled** (`CicsTask.rewindCounter` / `updateCounter` / `getCounter(.., reduce, cmpMin, cmpMax, fullword)`, the stub's `GGCRCNT` /
  `GGCRDCN` / `GGCUCNT` / `GGCUDCN` / `GGCGCNX` / `GGCGDCX`, the det translator and `equivalence_cics.py`): the counters of X30 / X45 / X50.
  A counter has reached its limit at MAXIMUM + 1 (where a GET leaves it). REWIND with no INCREMENT (or 1): at the limit it becomes its
  minimum, below it SUPPRESSED 102. UPDATE to a value from MINIMUM to MAXIMUM + 1. GET REDUCE: the value handed out, the counter MAXIMUM + 1.
  GET COMPARE tests the value handed out, a value out of range is SUPPRESSED 103 and the counter is unchanged (ASSUMED: IBM does not say
  whether it advances); it also tests a counter a scenario states (no limits entry). 201 / 403 / 404 as GET; a counter name is checked
  before the counter's existence, which before 406 (ASSUMED: the pages give no order).
- **What IBM leaves open, and what we do.** (1) UPDATE COMPAREMIN / COMPAREMAX: the options text compares "the current value to assign" (the
  new VALUE), SUPPRESSED 103 names "the current value of the named counter": REFUSED by name at translation. (2) REWIND INCREMENT above 1
  (within the range): how the limit test applies it is not stated; REFUSED at run time (1 and the default are modelled; an INCREMENT beyond
  the range is IBM's stated 406; zero has no meaning: REFUSED). (3) REDUCE with WRAP: which acts when the increment overshoots is not stated:
  REFUSED. (4) REDUCE, or COMPAREMIN / COMPAREMAX, on a counter already at MAXIMUM + 1: whether SUPPRESSED 101 or 103 comes first, and
  what REDUCE does with nothing left to reduce, is not stated: REFUSED (WRAP and plain GET at the limit are as X45 / X50). (5) The signed
  reading of a negative fullword VALUE or compare value (the open point of X30): REFUSED for COUNTER (a DCOUNTER holds it as a huge
  unsigned number: 406 / out of range). (6) REWIND / UPDATE of a counter with no limits entry (a scenario's): the limit it tests is not
  stated by the run: REFUSED. (7) NOSUSPEND: BUSY needs a coupling facility; this region has one task and no structure, so the option is
  accepted and ignored (ASSUMED); BUSY RESP2 500 and the 301-311 server errors are never returned. (8) The stub translator takes data
  areas only for REWIND INCREMENT, UPDATE VALUE and the compare bounds (the det translator takes literals). (9) INCREMENT beyond MAXIMUM -
  MINIMUM on GET stays X50's refusal (IBM's 406 boundary there is (maximum - minimum) + 1; the narrower refusal is kept).
- **Refused by name:** UPDATE COMPAREMIN / COMPAREMAX; BUSY RESP2 500; the rest above, each with its own message (spec `task.py`).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven on both runtimes scenario for scenario, once as COUNTER and
  once as DCOUNTER (tests/cics_crucible/test_counter_ops_runtimes_5039.py) and both translators
  (tests/cobol_mainframe/test_counter_ops_translate_5039.py). No corpus program runs these commands yet.

### X54. RECEIVE MAP into a DFHMDF JUSTIFY field: right-justified, zero or blank filled — ASSUMED (#5082)
- **What IBM documents** (CICS TS 6.x, DFHMDF, https://www.ibm.com/docs/en/cics-ts/6.x?topic=macros-dfhmdf , re-read 2026-10-14;
  RECEIVE MAP, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-receive-map). JUSTIFY "specifies the field justifications for input
  operations." "LEFT specifies that data in the input field is left-adjusted." "RIGHT specifies that data in the input field is
  right-adjusted." "BLANK specifies that blanks are to be inserted in any unfilled positions in an input field." "ZERO specifies that
  zeros are to be inserted in any unfilled positions in an input field." "If JUSTIFY is omitted, but the NUM attribute is specified,
  RIGHT and ZERO are assumed." "If JUSTIFY is omitted, but attributes other than NUM are specified, LEFT and BLANK are assumed."
  (The earlier wording of this entry paraphrased those sentences as quotes; the text above is the page's, as returned by the fetch
  tool's reader, which summarises -- re-check against the page in a browser before quoting it outside the register.)
  GRPNAME: "The ATTRB operand specified on the first field of the group applies to all of the fields within the group." "OCCURS and
  GRPNAME are mutually exclusive". PICIN: "the validity of the input data is not checked by BMS or the high-level language when the map
  is used"; PICOUT: "is like PICIN, except that a picture to be applied to an output field in the OUT or INOUT map is generated."
- **Modelled.** The text typed (without its trailing blanks) is placed at the right (RIGHT) or left (LEFT) end of the `<f>I` field,
  the rest filled with ZERO's `0` or blank; `<f>L` is the length of the text typed. Translator: `Cics.receive_map` reads the field's
  JUSTIFY off the generated screen's LAYOUT (`ScreenField.justify`, from the DFHMDF operand) and emits `DetJustify.place`;
  a field with no JUSTIFY still goes through `DetCics.typed`, so no existing port moves.
- **The oracle models it too** (`tests/tools/equivalence_cics.py` `map_input` / `bms_justify` / `justified`): the GnuCOBOL side's
  RECEIVE MAP input area is what BMS leaves in a field the corpus's BMS source says JUSTIFY (the engine's own reading of the
  DFHMDF, `ScreenField.justify`'s source), the length the text typed's. Without it the instrument handed the program the text
  left-justified and every port that is right read as differing (GenApp LGTESTP2 / LGTESTP4, `ENP2LIF` JUSTIFY=(RIGHT,ZERO)).
  The cics-crucible runner already justified its input (`cics_bms.received_value`).
- **Assumed.** (1) ZERO with LEFT fills trailing positions with `0` (IBM states the fill character, not the side it lands on for
  LEFT). (2) Text longer than the field is cut from the end the justification starts from (RIGHT keeps its last bytes). (3) The
  length is that of the text typed, before justification. IBM's DFHMDF page (re-read 2026-10-15) says nothing of what `<f>L` holds after justification. For a NUM field this
  matters (#5116): a program that reads `<f>I(1:<f>L)` sees the text's leading zeros, so cbsa-bnk1cac types its rates at the field's full width. (4) Input arriving through the CICS stub is the typed text, not a 3270
  data stream, so a null or `X'00'` in a field (BMS's erase-input convention) is not modelled.
- **NUM default (#5116).** A field with no JUSTIFY but ATTRB=NUM is right-justified and zero-filled, as IBM assumes. The forge's
  `_justify` returns the effective operand (`RIGHT,ZERO` for it), so `ScreenField.justify`, `Cics.receive_map`'s `DetJustify.place`
  and the oracle's `bms_justify` / `map_input` all take the one rule, and the cics-crucible runner (`cics_bms.received_value`)
  reads the same: an explicit JUSTIFY is as coded (LEFT / BLANK where a half is left out), so `JUSTIFY=(BLANK)` on a NUM field is
  left-justified. A NUM field's generated screen class now carries `"RIGHT,ZERO"` in LAYOUT; a port that RECEIVEs one moves.
- **JUSTIFY on SEND MAP: not applicable.** IBM: JUSTIFY "specifies the field justifications for input operations", so the output
  map keeps the program's text as is (SEND MAP is not modelled to justify, and need not be).
- **PICIN / PICOUT: out of scope, by name.** They are pictures given to the *generated symbolic-map field* (compile-time: the item's
  PICTURE in the copybook) and BMS does not check or convert the data at run time ("the validity of the input data is not checked by
  BMS"); no run-time conversion exists to model. The symbolic map's PICTURE is already what the layouts read.
- **Not modelled, by name.** (1) A GRPNAME group's later fields take the first field's ATTRB (so NUM, hence the NUM default); the
  forge reads each field's own ATTRB, so a group member without one is treated as non-NUM. (2) OCCURS: IBM gives every occurrence
  the field's one JUSTIFY, but a screen's OCCURS field is not received at all by `Cics.receive_map` (its values are keyed `NAME.n`,
  which `screen_fields` does not list) and the oracle refuses a symbolic map with OCCURS by name ("BMS OCCURS"); OCCURS and GRPNAME
  are mutually exclusive in IBM, so the two never combine.

### X55. Macro-level CICS and CICS Assembler programs: refused by name, not translated (#5121)
- **IBM.** The macro-level interface is the pre-command-level CICS API (the "era 0" of #5121: DFHxx macro calls, no
  EXEC CICS). IBM's DFHMSCAN utility ("Identify macro-level programs utility program", CICS TS reference) scans load
  modules for the DFH macro expansions of macro-level programs, and for the obsolete `EXEC CICS ADDRESS CSA` command;
  the assembler translation output (DFHEIENT / DFHEIRET) is the command-level assembler prologue / epilogue.
- **What we do.** Nothing translates them. `gitgalaxy/core/cics_macro_level.py` reads COBOL code lines and assembler
  sources and names two families: `macro-level CICS` (a `DFHxx TYPE=` macro with xx one of BMS BP DC DI FC IC JC KC PC SC SP
  TC TD TR TS WT, a COBOL `CALL 'DFHxx'`, `USING / COPY DFHCSADS / DFHTCADS / DFHCSA / DFHTCA`, `CSATCA`, `EXEC CICS ADDRESS CSA / TCA`)
  and `CICS Assembler` (DFHEIENT / DFHEISTG / DFHEIEND / DFHEIRET / DFHEIGBL or EXEC CICS in an assembler source, or any
  macro-level assembler program). `det/source.py` refuses a COBOL source by name before COPY expansion (so a missing
  DFHCSADS is not reported as a missing copybook); the feature inventory counts both families per estate
  (`refusal_families`), including `.asm` / `.mac` members; `refusal_map.json` maps each to its agreed refusal family.
- **Not refused.** Command-level EXEC CICS (COBOL or assembler without the above), DFHRESP / DFHVALUE, BMS map macros, and
  the macro TABLES (DFHFCT / PCT / PPT / DCT / TST ... `TYPE=`), which are resource definitions (cics_macro_tables.py).
- **Assumed (by name, #5158).** IBM's DFHMSCAN page does not enumerate the macro names, and no macro-level reference
  was read line by line for this list. Each family below is therefore ASSUMED, not cited; the one IBM-sourced item is the
  obsolete `EXEC CICS ADDRESS CSA / TCA` (DFHMSCAN). A family missing from the list is a missed detection, never a false
  refusal (every pattern needs the macro name and `TYPE=`). A new name is added to `MACROS` with a test, and to this table
  (`tests/core_engine/test_cics_macro_level.py` pins the two together).

  | Family | Macro | Status |
  |---|---|---|
  | BMS | `DFHBMS` | ASSUMED |
  | built-in functions | `DFHBP` | ASSUMED |
  | dump control | `DFHDC` | ASSUMED |
  | data interchange | `DFHDI` | ASSUMED |
  | file control | `DFHFC` | ASSUMED |
  | interval control | `DFHIC` | ASSUMED |
  | journal control | `DFHJC` | ASSUMED |
  | task control | `DFHKC` | ASSUMED |
  | program control | `DFHPC` | ASSUMED |
  | storage control | `DFHSC` | ASSUMED |
  | syncpoint | `DFHSP` | ASSUMED |
  | terminal control | `DFHTC` | ASSUMED |
  | transient data | `DFHTD` | ASSUMED |
  | trace control | `DFHTR` | ASSUMED |
  | temporary storage | `DFHTS` | ASSUMED |
  | wait | `DFHWT` | ASSUMED |
  | CSA / TCA addressing: `DFHCSADS`, `DFHTCADS`, `DFHCSA`, `DFHTCA`, `CSATCA` | COBOL `COPY` / `USING`, assembler operands | ASSUMED |
  | `EXEC CICS ADDRESS CSA / TCA` | COBOL command | IBM (DFHMSCAN) |
- **Census (#5158).** `det_survey.py` and `cics_census.py` count `.asm` / `.mac` / `.hlasm` / `.assemble` / `.bal` members with
  the COBOL programs: one survey row per member with evidence, refused with the same text det gives (`refused: macro-level CICS` /
  `refused: CICS Assembler` in the blocker report).

### X56. OS/VS COBOL BLL cells and SERVICE RELOAD, lowered onto the pointer lane by IBM's conversion to VS COBOL II — ASSUMED, REFUSED where IBM is silent (#5119, era 1)
- **What IBM documents** (CICS/MVS 2.1.2 Application Programmer's Reference, SC33-0512-1, March 1991, chapter 1.4, "Base locator for
  linkage (BLL)", pp. 21-23). "The parameter list must be defined as the first parameter to the program unless a communication area is
  being passed to the program, in which case the DFHCOMMAREA definition must precede it." "The first 02-level data name (that is,
  FILLER) is set up by CICS to provide addressability to the other fields in the parameter list. The other data names are known as BLL
  cells ... There is a one-to-one correspondence between the 02-level data names of the parameter list definition and the 01-level data
  definitions in the linkage section." "If a BLL cell is named in the SET option of a CICS command, subsequent reference to the
  corresponding data definition name will address the storage supplied by CICS." Large areas: "If an area greater than 4096 bytes is
  defined ... in the linkage section, additional statements may be required ... `ADD 4096 FRPTR GIVING FRPTR1` ... the usual one-to-one
  correspondence of BLL cells to the data areas is not maintained"; "No additional BLL cell is required if DFHCOMMAREA itself is larger
  than 4096 bytes." SERVICE RELOAD: it "must be used following each statement that modifies addressability to an area defined in the
  linkage section, that is, whenever the contents of a BLL cell is changed in any way"; "after a locate-mode input operation, the SERVICE
  RELOAD statement must be issued ... If areas larger than 4096 bytes are being addressed, the secondary BLL cells must first be reset
  before the SERVICE RELOAD statement is executed"; "If an address is moved into a BLL cell, addressability must be established in the
  same way, for example: `MOVE B-POINTER TO A-POINTER SERVICE RELOAD A-DATA.`" Chained areas: a paragraph name after the statement that
  changes a cell "causes the compiler to generate code to reestablish addressability"; without it the record still addresses the area
  it addressed before. The whole passage (p. 22, "BLL and chained storage areas"): "If access is required to a series of chained storage
  areas (that is, areas each of which contain a pointer to the next area in the chain), a paragraph name must be inserted immediately
  following any statement that establishes addressability to one of the storage areas", with the example `02 USERPTR PIC S9(8) COMP` in
  the list, `02 NEXTAREA PIC S9(8) COMP` in USERAREA, and `MOVE NEXTAREA TO USERPTR. ANYNAME. MOVE FIELD TO TESTVAL.`: "The second MOVE
  statement moves data from the newly addressed area, but only because a paragraph name follows the first MOVE statement. If no paragraph
  name is inserted, the reference to FIELD is taken as being to the storage area that is addressed when the first MOVE statement refers
  to NEXTAREA. Insertion of a paragraph name causes the compiler to generate code to reestablish addressability through USERPTR, so that
  the reference to FIELD (and the next reference to NEXTAREA) is to the newly addressed storage area." Conversion step 2 (p. 25): "Revise
  code that deals with chained storage areas to take advantage of the ADDRESS special register and POINTER variables"; step 6: "Remove
  artificial paragraph names where BLL cells are used to address chained storage areas". ADDRESS (p. 51): "If an ADDRESS command is included in a COBOL program that is to be compiled using the optimization
  feature, it must be followed by SERVICE RELOAD statements to reload the BLL cell being used."
- **IBM's conversion** (same book, "Converting to VS COBOL II", p. 29, and Figure 3, p. 26): "1. Remove, from the linkage section, the
  entire structure defining BLL cells and the FILLER field ... 3. Change every SET(BLL cell) option in CICS commands to SET(ADDRESS OF
  A-DATA) or SET(A-POINTER) where ... A-POINTER is defined with the USAGE IS POINTER clause. 4. Remove all SERVICE RELOAD statements. 5.
  Remove all program statements required in OS/VS COBOL to address structures in the linkage section longer than 4K bytes. A typical
  statement is: ADD 4096, D-PTR1 GIVING D-PTR2." VS COBOL II ignores a SERVICE RELOAD it is given (p. 24).
- **What the translator does** (`gitgalaxy/tools/cobol_to_java/det/bll.py`, run on the program's lines before det's own reading,
  `program._translate`, and on its text before the oracle's, `tests/tools/equivalence_cics.translate`). It applies that conversion in the
  SET(A-POINTER) form, keeping IBM's timing: the cells become POINTERs in WORKING-STORAGE (the record's base cells; the FILLER and the
  secondary cells go), `SERVICE RELOAD record` becomes `SET ADDRESS OF record TO cell` at the same place (so the record is addressed anew
  exactly where the program reloads it, and before that addresses what it addressed before, as IBM's compiler does), `SERVICE RELOAD` of
  the list itself or of DFHCOMMAREA, or in a program with no cell list, is nothing (`CONTINUE`), `ADD 4096 cell GIVING next-cell` is
  nothing, `MOVE cell TO cell` is `SET cell TO cell`. A pointer-lane program then (X47: GETMAIN SET, SET ADDRESS OF; DetCics / CicsTask in
  the port, the stub's GGCGETM and GnuCOBOL's own SET ADDRESS OF in the oracle). A SET(cell) of READ / READ UPDATE / READNEXT / READPREV /
  RECEIVE / RETRIEVE / READQ TS is then that command's SET(pointer) form (X58), with its own refusals.
- **Chained storage areas** (#5119). A record whose base cell changes (a SET option, MOVE cell TO cell, MOVE fullword TO cell) with no
  SERVICE RELOAD of it later in the same paragraph is reloaded from its cell at the head of every paragraph and section (IBM's compiler
  re-addresses at the procedure name however it is reached: falling into it, GO TO, PERFORM, a HANDLE exit); a paragraph that is only
  EXIT reads no record and is left alone. The oracle's reload is `SET ADDRESS OF record TO cell`; the det port's is `CALL 'GGCBLLR'`
  (`DetCics.bllReload`). An address moved between a cell and a fullword of data (`MOVE cell TO NEXTAREA`, `MOVE NEXTAREA TO USERPTR`) is
  `CALL 'GGCBLLP'` / `CALL 'GGCBLLG'`: the stub (ggcics.c) and CicsTask (`bllToken` / `bllPointer`, via DetCics.bllToData / bllFromData)
  hold the same token in the fullword.
- **Assumed.** (1) A program is a BLL program when its first LINKAGE 01 (its second, after DFHCOMMAREA) is a group of 4-byte binary
  integers led by a FILLER, and the program has a SERVICE RELOAD or names one of those fullwords in a SET or DATAPOINTER option; a list
  with no such evidence is ordinary data (the VS COBOL II reading of the same text). (2) A record past the last cell has no cell (IBM
  says nothing of too few cells); a SERVICE RELOAD of it is refused. (3) The secondary cells are checked where the record is reloaded in
  the paragraph that changed its base cell: IBM's "must first be reset". A reload in a paragraph that did not change the base (a HANDLE
  CONDITION exit's "SERVICE RELOAD statements ... at the start of the paragraph") takes the record whole from the base cell, as a program
  that reset its secondary cells earlier gets. (4) A cell's value is a handle, as X47's pointer's: SERVICE RELOAD of a record whose cell
  holds no address is refused at run time ("SET ADDRESS OF a null or unknown pointer"), where IBM's record would address storage that is
  not the program's. (5) An address held in data is a token, not the address: 0 for NULL, the n-th distinct address moved into data
  n * 65536 (at most 1525, so it keeps 8 digits), the same in both runtimes; the instrument's 8-byte addresses do not fit a fullword. A
  program that shows the fullword or computes with it is outside the proof (IBM's value is a real address); a value no cell gave moved back
  into a cell is refused at run time ("an address in data that no BLL cell gave"), so ADD 4096 to a token is never a wrong address. (6) A
  paragraph reload of a null cell leaves the det port's record as it was; GnuCOBOL's record is then null, so a program that uses it fails
  the proof (IBM's record would address location 0). (7) A reload at every paragraph name is IBM's chained-area text; IBM's OPTIMIZE
  (where SERVICE RELOAD is also required, p. 51) is not modelled apart.
- **Refused by name**, the whole program, every message "OS/VS COBOL BLL addressing: ...: not modelled": a cell used as a number (any
  mention but the idioms above, e.g. `IF USERPTR = ZERO`: the det translator refuses NULL in a condition); `MOVE` between a cell and an item
  that is not one plain fullword binary integer (PIC S9(8) COMP, no OCCURS above it), or into several items; a reload, or a paragraph
  name after a change, before a long record's secondary cells are reset; DECLARATIVES in a program whose records are addressed again at
  paragraph names; a paragraph name in a COPY member where records are addressed again; a secondary cell set by a command or a MOVE (only ADD 4096 sets one); `ADD
  4096` into a cell that is not the next secondary cell of the same record; a cell as a command's data (any option but SET, DATAPOINTER
  and ADDRESS's); `SERVICE LABEL` (the CICS translator's output, not source); `SERVICE RELOAD` of an item that is not a LINKAGE 01, or of
  a LINKAGE record no cell addresses; DFHCOMMAREA after the list (IBM: it must precede it); a level-77 / REDEFINES record among the
  addressed ones; a cell list, or a statement the lowering changes, in a COPY member. Each command's own refusals stay for a cell: RECEIVE
  SET without MAXLENGTH, RETRIEVE SET without LENGTH, READQ TS SET with a literal LENGTH, READ SET with RBA / RRN / XRBA, READNEXT /
  READPREV SET with LENGTH (X58), LOAD PROGRAM SET (#5042), ADDRESS CWA / TWA / TCTUA / CSA (#5079).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Proven end to end on a synthetic estate (a long record over two cells,
  written past 4096 bytes and aliased by a second record through MOVE cell TO cell; a chain of three GETMAIN areas linked through a
  fullword and walked through a paragraph name; READQ TS SET(cell): GnuCOBOL and the det port SEND the same hand-traced text). No corpus
  program uses BLL cells yet, so no port moves.

### X57. READQ TD / DELETEQ TD on an intrapartition queue — ASSUMED, REFUSED where IBM is silent (#5079)
- **READQ TD** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readq-td). "Each READQ TD consumes the record it
  reads": the read is destructive. QUEUE (1-4 characters), INTO or SET, LENGTH, NOSUSPEND, SYSID. Conditions: QZERO (23) "the queue is
  empty or the end has been reached"; QIDERR (44) the queue name cannot be found; LENGERR (22) the INTO area cannot hold the data or
  the length is invalid: a LENGTH below zero raises it and the queue is not read, a LENGTH of zero raises it and the queue is still
  read, a record longer than LENGTH is truncated to LENGTH and raises it; after a read LENGTH is set to the record's original length.
  NOTOPEN (19), IOERR (17) and INVREQ (16, "an extrapartition queue opened for output was named") concern extrapartition queues;
  QBUSY (25) only arises with NOSUSPEND or an active HANDLE; DISABLED, ISCINVREQ, LOCKED, NOTAUTH, SYSIDERR need a region the run does not
  have. The page lists no ENDFILE: QZERO is the end-of-queue condition, so ENDFILE is not modelled.
- **DELETEQ TD** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-deleteq-td). "Deletes all transient data in a queue": an
  intrapartition queue's records go; an extrapartition queue "cannot be deleted" and raises INVREQ (16); QIDERR (44) for a queue that
  cannot be found. LOCKED, DISABLED, NOTAUTH, ISCINVREQ, SYSIDERR: not modelled (one task, no security, no remote queue). IBM lists no
  RESP2 for any of them (so 0).
- **What the runtimes do.** An intrapartition queue is a first-in first-out list in the run (the stub's files under the TS root,
  `td-<hex of the name>/`, shared by the tasks of one conversation as TS queues are; `CicsTask.TempStorage.td`): a WRITEQ TD to a
  defined intrapartition queue appends its record as well as recording its event (the WRITEQ TD event is unchanged: queue, text,
  resp), READQ TD removes the first, DELETEQ TD empties the queue. The queue's TYPE comes from the case's CSD (`DEFINE TDQUEUE(Q)
  ... TYPE(INTRA|EXTRA)`: `tdqueues.cfg` has a TYPE column, `CicsTask.withTdQueueTypes`); with no CSD every queue is defined and
  intrapartition. READQ TD records an event on both sides ({queue, resp, data}: the text of what went INTO, none when nothing was
  read); DELETEQ TD records none, as DELETEQ TS does, and shows through the RESP and the reads after it. LENGTH of a data area is
  set on NORMAL and LENGERR with a record read; a literal or `LENGTH OF` is the most INTO takes and is set nowhere.
- **Assumed.** (1) A queue is empty before the task writes to it: IBM says nothing of records a queue holds when the region starts
  (a case cannot seed one yet). (2) A WRITEQ TD to an intrapartition queue is committed at once: no logical recoverability, so a
  SYNCPOINT ROLLBACK does not undo it and a read sees a write of the same task. (3) A WRITEQ TD of LENGTH 0 queues an empty record,
  which a READQ TD reads as length 0 with NORMAL.
- **Superseded in part (#5168, X61).** READQ TD SET, NOSUSPEND, extrapartition queues (NOTOPEN / INVREQ / input reads), INDIRECT queues, seeded queues
  and RECOVSTATUS(LOGICAL) are modelled there; what is refused below is the X57 state, kept for the forms X61 still refuses (SYSID, REMOTE).
- **Refused by name.** READQ TD of an extrapartition queue (IBM's NOTOPEN / IOERR / INVREQ depend on the queue's open state and
  on a data set the run does not have) and of a queue defined with a TYPE other than INTRA or EXTRA (INDIRECT, REMOTE) or none
  (stub and port stop at the statement, "not modelled"); DELETEQ TD of the same other types; SET (the address of CICS's copy of the
  data is not modelled), SYSID (a remote system is not modelled), NOSUSPEND (QBUSY needs a second task); a record moved past INTO
  (a READQ TD whose LENGTH exceeds INTO, as READ INTO's: GnuCOBOL lays the storage after INTO out unlike IBM's compiler, X6).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. The oracle is GnuCOBOL plus the stub, not z/OS.

### X58. SET(ptr) on RECEIVE, RETRIEVE, READQ TS, GET CONTAINER, READ, READNEXT and READPREV — ASSUMED, REFUSED where IBM is silent (#5042)
- **RECEIVE (3270 logical)** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-receive-3270-logical). SET "specifies the pointer reference
  that is to be set to the address of the data read from the logical unit or terminal ... The pointer reference is valid until the next
  receive command or the end of task"; "If you specify the SET option, the argument [LENGTH] must be a data area. When the data has been
  received, the data area is set to the length of the data". Modelled as the INTO form's (MAXLENGTH and LENGTH(data-area) required, as for
  SET(ADDRESS OF record), X15).
- **RETRIEVE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-retrieve). SET "specifies the pointer reference to be set to the address
  of the retrieved data"; "If you use SET you must also include LENGTH"; "If you specify the SET option, the argument must be a data area. On
  completion of the retrieval operation, the data area is set to the length" of the data. IBM states no end for the pointer.
- **READQ TS** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readq-ts). SET "specifies the pointer reference that is set to the address
  of the retrieved data. The pointer reference, unless changed by other commands or statements, is valid until the next READQ TS command or the
  end of task"; "If you specify the SET option, the LENGTH must be specified".
- **GET CONTAINER (CHANNEL)** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-get-container-channel). SET "specifies a data area in which
  the address of the retrieved data is returned"; FLENGTH is an output field "the length of the data in the container". "CICS maintains the data
  area until any of the following occurs: A subsequent GET CONTAINER or GET64 CONTAINER command with the SET option, for the same container in
  the same channel ... The container is deleted by a DELETE CONTAINER command. The container is moved by a MOVE CONTAINER command. The channel
  goes out of program scope. The channel, and the containers that are in it, are deleted by a DELETE CHANNEL command. ... Do not issue a FREEMAIN
  command to release this storage." IBM does not say what the pointer sees when a PUT CONTAINER changes the container while it is held.
- **READ** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-read). SET "indicates that CICS is to supply a buffer where the record is read,
  and specifies the pointer reference that is to contain the address of the retrieved record ... The pointer reference is valid until the next READ
  command for the same file or until completion of a corresponding REWRITE, DELETE, or UNLOCK command, or a SYNCPOINT in the case of READ UPDATE
  SET." LENGTH "contains the actual length of the record" on completion.
- **READNEXT / READPREV** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readnext, summary-readprev). SET "specifies the pointer reference that
  is to be set to the address of the retrieved record ... valid until the next READNEXT or READPREV command specifies SET for the same browse (REQID)
  for the same file. The pointer is no longer valid after an ENDBR or SYNCPOINT command."
- **What the runtimes do.** One shape in both: `CicsTask.acquireSet(key, data, syncEnds)` (the stub's `blk_set_new`) makes a block of kind "received"
  (X47) holding a copy of the data, keyed by what ends it, and `invalidateSet(key)` (`blk_invalidate`) ends it; the commands that end a pointer
  call it where they complete (REWRITE, DELETE, UNLOCK, ENDBR, DELETE CONTAINER, MOVE CONTAINER, DELETE CHANNEL, SYNCPOINT). The port's
  `DetCics.setBlock` stores the handle in the pointer item; the stub's entry points are GGCRECP, GGCRTRS, GGCRDQS, GGCGETS, GGCRDST, GGCRDNS and
  GGCRDPS, each answering as the INTO form does (the same conditions and events) and then registering the block. The blocks are the root task's, so
  a program LINKed to sees and ends the pointers of the one that called it, as the stub's one process does.
- **Assumed.** (1) After its end IBM calls a pointer "no longer valid" and says nothing of the storage: here it reads as zeros through a record already
  addressing it, in both runtimes (a program that reads through an ended pointer is outside the proof; a record is not told when its pointer ends).
  (2) RETRIEVE's pointer lasts to the task's end. (3) A condition that delivers no data (LENGERR with RECEIVE keeps the truncated data, which is
  delivered; ENDDATA, ENVDEFERR, ITEMERR, QIDERR, CONTAINERERR, NOTFND, ENDFILE ...) leaves the pointer as it was. (4) READ UPDATE SET: the pointer
  ends at SYNCPOINT (IBM's words), a plain READ SET's does not; a REWRITE / DELETE / UNLOCK that completes ends the READ SET pointers of its file
  whichever record they hold (IBM: "a corresponding" one; a DELETE by RIDFLD counts). A command that fails ends nothing. (5) A browse pointer's key is
  the file: this runtime has one browse per file and no REQID (REQID is refused). (6) The terminal's data is delivered as the INTO form's: the first
  MAXLENGTH bytes (NOTRUNCATE keeps the rest for the next RECEIVE, which ends the pointer). (7) The stub reads a record or item into its own 32768 bytes
  (the INTO form's buffer); a longer one is refused there.
- **Refused by name.** At translation: SET together with INTO (or NODATA); RETRIEVE SET / READQ TS SET without LENGTH, GET CONTAINER SET without
  FLENGTH (IBM: a data area), a literal LENGTH there; READ SET with a literal LENGTH, with RBA / RRN / XRBA (a relative-byte record) and READNEXT /
  READPREV SET with LENGTH or RBA (the browse forms' INTO LENGTH rule); BYTEOFFSET with GET CONTAINER SET; a pointer that is not a plain USAGE POINTER
  item or that a REDEFINES overlays (X47); SET ADDRESS OF / ADDRESS OF as X47. At run time: FREEMAIN of one of these blocks (IBM: not GETMAIN's; for GET
  CONTAINER SET it says do not); a PUT CONTAINER or MOVE CONTAINER onto a container while its GET CONTAINER SET pointer is held; a block above 256
  MiB. Still refused, and why: SEND MAP / RECEIVE MAP / SEND CONTROL SET (a BMS output / input buffer, a different mechanism), LOAD PROGRAM SET (the
  loaded bytes), GETMAIN64 / FREEMAIN64 / GET64 CONTAINER (64-bit storage).
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven only (see `reached`): no cics-crucible case or estate program exercises it
  yet (cics-crucible C2 covers RECEIVE / RETRIEVE SET and C3 / C4 are the container and file cases still to land), so no port moves and no ZECS program
  is made whole by this entry.

### X59. ADDRESS EIB / COMMAREA modelled; ADDRESS CWA / TWA / TCTUA / ACEE, SEND PAGE, PURGE MESSAGE, terminal CONVERSE, POST and WAIT EVENT refused by name (#5079)
- **ADDRESS** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-address). EIB "returns a pointer reference set to the address
  of the EXEC interface block (EIB)"; COMMAREA "returns a pointer reference, set to the address of the communication area (COMMAREA) available
  to the currently executing program"; "If the COMMAREA does not exist, the pointer reference is set to the null value, X'FF000000'". CWA, TWA,
  TCTUA (of the principal facility) and ACEE return the address of the common work area, transaction work area, terminal control table user
  area and access control environment element; a missing one is set to the same null value. The page lists no condition (RESP / RESP2 /
  NOHANDLE are the common options) and has no COBOL note.
- **What the runtimes do.** The det port lowers EIB to `DetCics.setPointerToRecord(task, ptr, DFHEIBLK)` and COMMAREA to
  `DetCics.addressCommarea(task, ptr, DFHCOMMAREA, EIBCALEN)`; the stub's `GGCADDR` stores the address of the EIB or of the program's
  DFHCOMMAREA in the pointer. The port's pointer holds the handle of the record's own bytes (X47), the stub's a real address, so SET ADDRESS OF
  record TO pointer makes the record and the EIB (or the DFHCOMMAREA) one storage in both. EIBRESP and EIBRESP2 are written NORMAL, and RESP /
  RESP2 as for any command. Several options in one command are taken in the order EIB, COMMAREA.
- **Assumed.** (1) The EIB the pointer addresses is the task's own, updated by every later command as the program's DFHEIBLK is. (2) The
  COMMAREA the pointer addresses is the program's DFHCOMMAREA (the area the caller passed, X23), at its start. (3) The command raises no condition
  (the page lists none).
- **Refused by name.** At translation: CWA, TWA, TCTUA and ACEE (the region defines none: no CICS system tables), the old ADDRESS SET form,
  ADDRESS COMMAREA in a program with no LINKAGE 01 DFHCOMMAREA (there is no record to address; the pointer could only be handed to SET ADDRESS OF
  another record), ADDRESS with neither EIB nor COMMAREA, a pointer that is not a plain USAGE POINTER item or that a REDEFINES overlays (X47). At
  run time: ADDRESS COMMAREA when EIBCALEN is 0 (IBM's X'FF000000' is not NULL, and a handle is no number the program can compare with it). BLL cells
  (OS/VS COBOL, X56) keep ADDRESS TWA / CWA a hole for the same reason.
- **The old-style sweep (refused whole, by name; each with its own reason in `standards/cics/commands/api.py`).**
  - **SEND PAGE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-page): "completes a BMS logical message" and "causes BMS to
    generate a device-dependent data stream for the last (perhaps the only) page of data"; RETAIN / RELEASE, OPERPURGE; conditions IGREQCD,
    INVREQ, RETPAGE, TSIOERR, WRBRK. **PURGE MESSAGE** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-purge-message) "discontinues the building of a BMS logical message" and
    "deletes the current logical message, including any pages of device-dependent data stream already written to CICS temporary storage". Both
    belong to the ACCUM / PAGING message SEND MAP and SEND TEXT refuse: there is no message to complete or purge, and paging to a terminal
    operator (the page the operator views, RETPAGE) is a terminal dialogue the region does not run.
  - **CONVERSE** on a terminal (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-converse-default): FROM "specifies the data to be written to the terminal", INTO / SET "the receiving
    field for the data read from the terminal", TOLENGTH / TOFLENGTH the length to receive, MAXLENGTH / MAXFLENGTH the most to recover (truncated
    with LENGERR). A send followed by a receive of the operator's reply; the region's terminal input is one stated screen per task (RECEIVE, X15),
    and IBM's page does not say what a reply is when the send was not a complete dialogue step. Refused until a case needs it (the CONVERSE
    of CICS web support, WEB CONVERSE, is X35, and APPC CONVERSE is distributed processing).
  - **POST** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-post): "requests notification that a specified time has expired"; CICS makes a 4-byte timer-event control area available,
    its address in the SET pointer; INTERVAL / TIME, REQID. **WAIT EVENT** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-wait-event): "synchronizes a task with the completion of an
    event initiated by the same task or by another task", ECADDR the timer-event control area that "must be posted before task activity can be
    resumed". A POSTed area is posted by the clock, a WAIT EVENT gives the processor to another task: the region runs one task at a time and has
    a stated clock that does not move while a task waits (a DELAY takes no time, X4), so a timer that expires during a wait has no meaning here and the posting and the wait are refused.
    WAIT EXTERNAL and WAITCICS stay name-only with the same reason.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Reached by no corpus program yet (0 uses in the 18 corpora, #5079), so no
  port moves and no ZECS program is made whole by this entry. cics-crucible cases to add (separate queue items): ADDRESS EIB / COMMAREA with the
  EIB view reading EIBRESP after a command and a COMMAREA view written through; ADDRESS COMMAREA with no COMMAREA (refused).

### X60. ENQ fault injection: ENQBUSY with NOSUSPEND, RESP2 0 — ASSUMED, REFUSED where IBM is silent (#5089)
- **What IBM says** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-enq). "If a resource is not available when ENQ
  is issued, the application program is suspended until it becomes available. However, if the NOSUSPEND option has been specified and the
  resource is unavailable, the ENQBUSY condition is raised, as it is also raised if you have an active HANDLE CONDITION." Conditions:
  "55 ENQBUSY occurs when an ENQ command specifies a resource that is unavailable and the NOSUSPEND option is specified, or there is an
  active HANDLE CONDITION ENQBUSY. If the NOSUSPEND option is not specified ... the application program is suspended and the ENQBUSY
  condition is not raised. Default action: ignore the condition." The page lists no RESP2 for ENQBUSY. INVREQ RESP2 2 (MAXLIFETIME with an
  incorrect CVDA) and LENGERR RESP2 1 (LENGTH outside 1 through 255) are the other two conditions.
- **Modelled** (`CicsTask.enq`, the stub's `GGCENQ`, the det translator and `equivalence_cics.py`): one task in the region, so an ENQ is
  NORMAL, unless a scenario's `faults` plans `{"cmd": "ENQ", "resource": "WS-RES", "resp": "ENQBUSY"}` (with `nth` as every fault):
  then the ENQ sets RESP 55, RESP2 0, and records the event `ENQ resource=.. resp=..`. A fault names the resource as the RESOURCE operand is
  written (upper case, blanks dropped). An ENQ that does not fault records no event, as before.
- **What IBM leaves open, and what we do.** (1) RESP2 of ENQBUSY: IBM gives none: 0 (ASSUMED, as every command that states none); a plan
  naming one is REFUSED. (2) A HANDLE CONDITION ENQBUSY makes IBM raise the condition without NOSUSPEND too; the runtimes do not read that
  state, so a planned-busy ENQ without NOSUSPEND is REFUSED at run time, handler or not. (3) Which resource another task holds, how long, and
  whether a RUN child's DEQ frees it: no second task holds anything in this region; the plan states only that the resource is busy at this
  ENQ. (4) INVREQ 2 / LENGERR 1 are not planned: the translated program raises them from its own operands, and neither runtime checks
  LENGTH or MAXLIFETIME today (an out-of-range LENGTH still returns NORMAL; a sibling gap, not a plan).
- **Refused by name:** the list in the summary.
- **Status:** ASSUMED for RESP2 0, REFUSED where listed. Unit-proven on both runtimes (tests/cics_crucible/test_enq_fault_5089.py).

### X61. Transient-data queues past X57: READQ TD SET / NOSUSPEND, extrapartition input queues, RECOVSTATUS(LOGICAL), INDIRECT, seeded queues — ASSUMED, REFUSED where IBM is silent (#5168)
- **READQ TD** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readq-td). SET "sets a pointer reference to the address of the data
  read ... The pointer stays valid until the next READQ TD or the end of the task". NOSUSPEND: "if the queue is already in use for output, the
  task is not suspended"; QBUSY (25) "occurs when READQ targets a logically recoverable intrapartition queue that another task is writing to
  or deleting from, and no committed records remain". NOTOPEN (19): "the destination is closed" (extrapartition only); INVREQ (16): "an
  extrapartition queue opened for output was named"; IOERR (17): an input/output error, "the data record in error is skipped"; QZERO (23):
  "the queue is empty or the end of the queue has been reached". The page lists no RESP2.
- **TDQUEUE definition** (https://www.ibm.com/docs/en/SSJL4D_6.x/reference-system-management/resources/tdqueue/dfha4_summary.html). RECOVSTATUS
  (intrapartition): NO "not recoverable"; LOGICAL "changes are restored to the state at the end of the last completed unit of work"; PHYSICAL "if
  emergency restart occurs, ... recovered to its status at the time CICS terminated", the last READQ backed out if its unit of work did not commit.
  OPENTIME (extrapartition): INITIAL opened at install time, DEFERRED "remains closed until you indicate that you want to open it" (CEMT / SET
  TDQUEUE). TYPEFILE: INPUT, OUTPUT or RDBACK ("an extrapartition queue can be input or output, but not both"). INDIRECTNAME: "the name of the
  transient data queue to which this indirect queue routes data"; the target "can be intrapartition, extrapartition, remote, or indirect".
  TRIGGERLEVEL: default 1, "specify a trigger level of 0 if you want to disable ATI processing"; TRANSID: "the transaction that is to be
  automatically initiated when the trigger level is reached".
- **What the runtimes do.** The stub reads each definition's attributes from `tdqueues.cfg` (`NAME TYPE KEY=VALUE ...`; the harness writes only the
  ones the CSD states, `csd_tdqueue_attrs`), CicsTask from `withTdQueueAttributes`. READQ TD SET is the INTO form's read (same conditions, same
  event) followed by a block of the record (`GGCRDTS`; `DetCics.setBlock` with the key `READQ TD`, so the next READQ TD ends it). An open
  extrapartition input queue reads the records a case seeds (the case's or scenario's `"td": {"QUEUE": [record, ...]}`, ASCII text; the stub's
  `ts/td-<hex>/NNNNNN.bin`, `CicsTask.TempStorage.seedTd`) exactly as an intrapartition queue does. A LOGICAL queue's first read, write or delete
  since the last SYNCPOINT saves it (the stub's `td-<hex>.uow`); SYNCPOINT drops the copy, SYNCPOINT ROLLBACK restores it. An INDIRECT queue is
  followed to its target before the CSD lookup, the QIDERR test, the records and the recoverability; the READQ-TD / WRITEQ-TD event keeps the
  queue name the program gave.
- **Assumed.** (1) NOSUSPEND has no effect: one task at a time touches a queue, so QBUSY cannot arise. (2) RECOVSTATUS not stated, or NO, is
  committed at once (IBM states no default; this is X57's assumption (2)). (3) A task reads its own uncommitted writes to a LOGICAL queue (IBM
  speaks of other tasks only). (4) OPENTIME not stated is INITIAL. (5) A task's abend (one no HANDLE ABEND exit takes) backs a LOGICAL queue out to its state at the last SYNCPOINT, in the
  stub and in CicsTask alike (IBM: "restored to the state at the end of the last completed unit of work"; a PHYSICAL queue touched since
  is refused); an abend taken by an exit backs nothing out. CicsTask refuses only a SYNCPOINT ROLLBACK after a SYNCPOINT (files).
  (5b) WRITEQ TD to an extrapartition queue with no TYPEFILE (or RDBACK) is taken as open for output, as before; only TYPEFILE(INPUT)
  and OPENTIME(DEFERRED) change the answer. (6) A queue defined TRIGGERLEVEL(n) with a TRANSID counts the records it holds
  (seeded ones included) plus the one being written. (7) The data set behind an input queue holds exactly the case's records and has no
  read error.
- **Refused by name** (stub and port stop at the statement, "not modelled"). SYSID (a remote system) and a queue of TYPE REMOTE; IOERR (no data
  set to fail); an extrapartition queue with no TYPEFILE or with RDBACK; SYNCPOINT ROLLBACK after a read, write or delete of a RECOVSTATUS(PHYSICAL)
  queue (what IBM backs out of a READQ is not specified further); a WRITEQ TD that brings a queue with a TRANSID to its TRIGGERLEVEL (automatic
  task initiation starts a task the run does not model); an INDIRECT queue with no INDIRECTNAME, whose target the CSD does not define, or in a
  chain that loops; READQ TD INTO with SET; SET without a LENGTH data area (IBM's SET page for the TS form says LENGTH "must be specified"; the TD
  page states no more than the record's length goes there), or with a literal LENGTH. IOERR on a write is not modelled (no data set to fail); a write to an open output queue records the event and
  writes nothing.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. The oracle is GnuCOBOL plus the stub, not z/OS.

### X62. CICS runtime resource state (CEDA / CEMT / CEDA INSTALL) is not read: only resource-definition sources are (#5154)
- **IBM.** CEDA defines and installs resource definitions in a running region and CEMT inquires on and sets installed
  resource state; the installed state lives in the region and its catalogs, not in a repository file.
- **What we do.** `gitgalaxy/core/cics_macro_tables.py` and the CSD reader lift definitions only. `GalaxyIR.resource_conflicts`
  already says that "CICS installs whichever is loaded last, which the source tree cannot say".
- **Refused.** Any claim that a resource is installed, enabled, or has a given runtime value. A dump of CEMT / CEDA output
  placed in a repository is not a definition source and is not read.
- **Assumed.** Nothing: the refusal needs no assumption. SIT start-up overrides (SIT=, GRPLIST=) that select which
  tables load are kept as text in the SIT row's `attributes`; which of them is in effect at start-up is not decided here.

## Language Environment

### L1. CEEDAYS — MATCHED where documented, a blank picture tail ASSUMED, REFUSED otherwise
- **What IBM documents** (Language Environment Programming Reference, "CEEDAYS -- Convert date to Lilian format"; the
  ILE copy of the same service, https://www.ibm.com/docs/en/ssw_ibm_i_73/apis/CEEDAYS.htm, says the same): a date that
  is not valid returns Lilian 0 and a nonzero feedback code; "After a valid date is parsed, remaining characters are
  ignored"; the input may carry leading or trailing blanks.
- **Modelled** (`tests/equivalence/le/ceedays.c`, `cobolrt/le/Ceedays.java`). Pictures made of `YYYY`, `MM`, `DD` in
  any order, or `YYYY` and `DDD` (Julian), each token once, adjacent or each pair joined by one separator character
  (`-`, `/` or `.`) used throughout. Feedback: 2507 date shorter than the picture's span, 2508 day not valid (a day
  outside its month, 29 February of a year that is not a Gregorian leap year, a Julian day 0 or past 365 / 366),
  2513 before 15 October 1582, 2520 non-numeric data or a separator that is not the picture's. The date past the span
  is never read (IBM: remaining characters are ignored).
- **Assumed (owner decision 2026-10-14).** The picture's own characters after its last token, **only when they are all
  blanks**. IBM does not say how they are read; CardDemo pads picture and date to 10 (`'YYYYMMDD  '`), and a blank tail is
  taken as ignored. The date past its span is IBM-documented ignored; the picture's tail is not, hence the narrow
  assumption. The tail is read: every byte from the last token to the declared length must be a blank, and a byte that
  lies past the picture item (a declared length that overruns it) is foreign storage, never trusted as a blank.
- **Refused (exit 98).** A picture tail with any non-blank byte (`'YYYYMMDDX'`, `'YYYYMMDD00'`, a complete set of
  tokens followed by more tokens) and a tail that overruns its item: CRECUST's `DATE-OF-BIRTH-FORMAT` is a halfword
  length of 10 over the 8 bytes `'YYYYMMDD'`, so its 2 extra bytes are the storage that follows the item, which z/OS
  would read as picture text. CRECUST's create-customer and born-in-the-future scenarios are refused by name, so
  cbsa-crecust stays unproven (and BNK1CCS, which LINKs it); born-before-1601 ends before CEEDAYS. A numeric month outside 1–12 (2508 vs 2517: IBM documents CEE2517 for a month not recognized
  but not what a numeric 13 is); a trailing blank on the part of the date the picture covers (whether it is 2507 or 2520, #4049;
  a blank inside it is a non-numeric position, 2520, and date bytes past the span are ignored); `YY` (a century window), month names, eras, a null or blank picture, a repeated or
  incomplete picture, a blank or mixed separator, `DDD` together with `MM` or `DD`.
- **Broadened by #4952.** CardDemo's `'YYYYMMDD  '` (picture and date padded with blanks to 10) used to be refused as a
  picture inside a longer field; it is modelled now (the span is read, the blank tail ignored), which is the assumption
  above and nothing wider. The test table is `tests/cobol_mainframe/test_det_ceedays.py`.
- COACTUPC's cursor placement after its date fields is unreached until z/OS settles the month-range case.

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

### L4. CEEIGZCT — a GitGalaxy-written stand-in, only where the estate has none
- **What.** IBM's Language Environment copybook CEEIGZCT is not in any estate and is never shipped. The translator
  ships `det/copy/CEEIGZCT.cpy`, written from IBM's public documentation, as a system member (like DFHAID): it is
  used only where the estate holds no CEEIGZCT of its own, and it refuses nothing else.
- **What it declares.** One condition name, `88 CEE000 VALUE X'0000000000000000'`: the symbolic feedback code for
  "the service completed successfully", the first 8 bytes of a condition token (severity 0, message 0). CBSA CRECUST
  copies it under `02 CONDITION-TOKEN-VALUE` (8 bytes: severity, message number, case / severity / control byte, facility ID) of its 12-byte `FC` group (the 8, then the 4-byte `I-S-INFO`) and tests `IF NOT CEE000 OF FC` after its
  CEEDAYS and CEELOCT calls. Every other CEE symbolic code stays undeclared: a program using one is refused by the
  engine as before (a stand-in is written only where the runtime behind a name is modelled).
- **Assumed.** That CEE000 is the all-zero token. IBM documents the symbolic codes as the first 8 bytes of the
  token and CEE000 as severity 0 / message 0; the all-zero value is our reading, and it agrees with the 12 zero bytes
  our CEEDAYS model writes on success (L1). A COBOL group compared with a longer or shorter token would pad with
  spaces; the comparison is of CRECUST's 8-byte `CONDITION-TOKEN-VALUE`, the first 8 bytes of the token.
- **Not modelled.** CEELOCT is modelled since #4884 (L5). CRECUST's `FC` is 12 bytes, the size of the token LE writes
  (`CONDITION-TOKEN-VALUE` 8 + `I-S-INFO` 4: #4952 checked the translated layout, `Field.group(s_FC, 0, 12)`), so CEEDAYS and CEELOCT
  overrun nothing; the earlier note that it was 8 bytes was a misreading of the 8-byte group inside it. Reached
  by `cbsa-crecust`.
- **IBM references.**
  - Using symbolic feedback codes: https://www.ibm.com/docs/SSLTBW_2.4.0/com.ibm.zos.v2r4.ceeam00/symfd.htm
  - Feedback code (the last parameter of every LE callable service):
    https://www.ibm.com/support/knowledgecenter/en/SSLTBW_2.1.0/com.ibm.zos.v2r1.ceea200/clcdt5.htm
  - Language Environment runtime messages (CEE0000I, symbolic feedback code CEE000):
    https://www.ibm.com/docs/SSLTBW_3.2.0/com.ibm.zos.v3r2.ceea900/lemes.htm

### L5. CEELOCT — the run's pinned clock as local time; seconds and the Gregorian tail assumed
- **What IBM documents** (Language Environment Programming Reference, "CEELOCT -- Get current local time"; the
  COBOL example). `CALL "CEELOCT" USING output_Lilian, output_seconds, output_Gregorian, fc` returns the local time as
  a Lilian date (days since 14 October 1582, a fullword binary), a Lilian timestamp (seconds since 00:00:00 on
  14 October 1582, a COMP-2) and a Gregorian string of the form YYYYMMDDHHMISS999.
- **Modelled.** `tests/equivalence/le/ceeloct.c` (COBOL side, linked into every case like CEEDAYS) and
  `cobolrt/le/Ceeloct.java` (the port) read the case's pinned clock (`COB_CURRENT_DATE` / the run's
  `FUNCTION CURRENT-DATE` text) and write the same values; the feedback code is 12 zero bytes (CRECUST's `FC` is 12
  bytes, L4). Without a pinned clock the C model refuses (exit 98).
- **Assumed.** (1) The local time is the pinned clock itself: the case's zone is the mainframe's. (2) output_seconds is
  `days x 86400 + time of day`, with the hundredths as a fraction. The Java side stores it by value in the item's own
  usage (HFP, C6), the C side as a native IEEE double; the byte patterns differ, which is why the translator passes
  the item by value and any other use of its bytes stays refused (C6). (3) IBM's Gregorian field is longer than the
  17 characters of the documented form; only the 17 are written, and what the remaining bytes hold is not documented
  (CRECUST's item is 17 bytes). (4) A leap second, a DST fold or an unset clock are not modelled.
- **IBM references.** https://www.ibm.com/docs/en/SSLTBW_2.1.0/com.ibm.zos.v2r1.ceea800/cblex1.htm (the COBOL example).

### L6. CEEGMT / CEEUTC, CEEDATM, CEESECS, CEEDATE, CEEISEC, CEEQCEN — IBM's conditions where documented; the clock, the output item and what IBM leaves open assumed or refused
- **What IBM documents** (Language Environment Programming Reference, the callable services; the message lists below are
  those IBM publishes for the same services as the ILE CEE APIs, which share their definitions and message numbers:
  https://www.ibm.com/docs/en/ssw_ibm_i_73/apis/CEEDATM.htm, `CEESECS.htm`, `CEEDATE.htm`, `CEEISEC.htm`, `CEEUTC.htm`
  (CEEGMT is its alias), `CEEQCEN.htm`). A Lilian date is the days since 14 October 1582 (15 October 1582 is day 1,
  16 May 1988 is day 148 138); a Lilian second counts from 00:00:00 on 14 October 1582 (second 86 401 is 00:00:01 on
  15 October 1582; 19:00:01 on 16 May 1988 is 12 799 191 601), a COMP-2, the valid range 86 400 to
  265 621 679 999.999 (31 December 9999). Every service ends with a 12-byte feedback token.
  - **CEEGMT / CEEUTC** `(output_Lilian, output_seconds, fc)`: the current UTC as a Lilian date and Lilian seconds.
  - **CEEDATM** `(input_seconds, picture_string, output_timestamp, fc)`: CEE2505 the seconds are out of range
    (output_timestamp then all blanks); CEE2518 the picture is not valid; CEE2527 the timestamp is truncated.
  - **CEESECS** `(input_timestamp, picture_string, output_seconds, fc)`: a full date is required, a time omitted is
    zeros, the rest of the string past the picture is ignored, a delimiter lets leading zeros go; on an invalid value
    output_seconds is 0 and the code is CEE2508 day, CEE2510 hour, CEE2513 Lilian date (before 15 October 1582),
    CEE2515 millisecond, CEE2516 minute, CEE2517 month, CEE2519 second, CEE2521 year, CEE2525 timestamp picture
    mismatch.
  - **CEEDATE** `(input_Lilian_date, picture_string, output_char_date, fc)`: valid 1 to 3 074 324; CEE2512 otherwise,
    output blanks; a picture with time characters outputs zeros for the time (IBM's sample: day 148 142,
    `YY/MM/DD HH:MI:SS.99`, `88/05/20 00:00:00.00`).
  - **CEEISEC** `(year, month, day, hours, minutes, seconds, milliseconds, output_seconds, fc)`: fullword inputs,
    year 1582-9999, month 1-12, day 1-31, hours 0-23, minutes 0-59, seconds 0-59, milliseconds 0-999; output 0 and
    CEE2510 hour, CEE2511 day, CEE2513 Lilian date, CEE2514 Lilian year, CEE2515 millisecond, CEE2516 minute,
    CEE2517 month, CEE2519 second.
  - **CEEQCEN** `(century_start, fc)`: the ILE default window starts 80 years before the system date and the value
    is 80.
- **Modelled.** `tests/equivalence/le/le_time.c` (COBOL side, linked into every case like CEEDAYS) and
  `cobolrt/le/LeTime.java` with the thin classes `Ceegmt`, `Ceeutc`, `Ceedatm`, `Ceesecs`, `Ceedate`, `Ceeisec`, `Ceeqcen`
  (the port): the same Lilian arithmetic, the same codes, the same refusals. The token is the CEEDAYS one (L1):
  severity 3, the message number, `0x59`, `CEE` in EBCDIC, zero on success. Pictures modelled: `YYYY YY MM DD DDD HH
  MI SS 99 999` and punctuation. An output is cut to hundredths / milliseconds, never rounded (IBM's sample: 661.986
  with `99` is `.98`). The translator reads and stores every COMP-2 argument by value (`gen.LIBRARY_FLOATS`: the
  HFP / IEEE bytes differ, C6) and passes the run's clock to CEEGMT / CEEUTC as it does to CEELOCT (L5).
  `tests/cobol_mainframe/test_det_le_time.py` runs one table of IBM's own samples and every documented condition,
  one invalid field at a time, through both sides.
- **Assumed.** (1) CEEGMT's GMT is the pinned clock: the det runtime's CURRENT-DATE carries offset +0000 and the
  oracle's case clock is read as GMT; a zone is not modelled (no CEEGMTO / CEEUTCO, below). (2) Output_timestamp and
  output_char_date (CEEDATM, CEEDATE) are halfword-prefixed VSTRINGs in COBOL: the model writes the length then the
  text and touches nothing past it; a failing call writes a zero length and leaves the text. IBM says the output is
  blanks on error and cut to the output's length (CEE2526 / CEE2527) but states no COBOL layout for an output declared
  `PIC X(n)`, as BANKDATA's `DATM-CONV` is (it reads `DATM-CONV(1:14)` only in a debug line). The Java side refuses an
  output item shorter than the result (the C model cannot see the item's size), so 2526 / 2527 are never produced.
  (3) The milliseconds of a Lilian second are the fraction floored to a thousandth, so a value in `.9995` is `.999`;
  a seconds value is valid below 265 621 680 000. (4) CEESECS answers CEE2525 (picture mismatch) for a non-digit in
  a numeric position or a delimiter that differs from the picture's: IBM names the code, not its trigger. (5) A
  value that is not exact in both HFP and IEEE (`.12`) can differ in the last bits; only the millisecond is compared.
- **Refused (exit 98, "NAME: ... is not modelled"), because IBM leaves it open or the model has no rule for it.**
  A picture with names (`Mmm`, `Www`), `AP`, Z-suppression, eras (`<JJJJ>`, `<CCCC>`), `RRRR`, a lone `Y` / `M` /
  `D` / `H` / `S` / `9`, a repeated token, or none (IBM: the country default). CEEISEC and CEESECS with **more than
  one** invalid field (IBM lists the codes, not their order). CEESECS: a timestamp shorter than its picture (IBM
  lists no insufficient-data code for it), with a leading blank, with leading zeros omitted after a delimiter
  (`1988-5-16`: IBM accepts it; the model has no rule), `YY` (the century window, which depends on the system date;
  CEEQCEN's 80 is the default, no CEESCEN is modelled) or `DDD` in the input, or a picture without a full date.
  CEEGMT without a pinned clock.
- **Not modelled: sibling services** of the same set: CEEUTCO / CEEGMTO (the offset from UTC, zone), CEESECI,
  CEEDYWK, CEESCEN, CEEFMDA / CEEFMDT / CEEFMDV (a call is refused by name by the translator, as before), and the
  country-default pictures.
- **IBM references.** The pages above; CEELOCT's example (L5) and the symbolic feedback codes (L4).

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
  Commit the entry file only: this page is not committed (#5057). A PR's CI renders it (it must render, the same way
  twice) and shows the diff; after merge it is published to the `generated` branch. `python tests/tools/register.py
  render` writes a local copy to read.
