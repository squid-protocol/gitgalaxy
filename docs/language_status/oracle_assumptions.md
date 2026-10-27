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
| C5 | compiler | `NUMPROC(MIG)` as Enterprise COBOL 5+ compiles it (NOPFD), `NUMPROC(PFD)` with preferred signs (#4271); `TRUNC(OPT)` with conforming binary values, `ARITH(EXTEND)` with intermediates within 30 digits (#4706); `INTDATE(LILIAN)` | MATCHED (NUMPROC) / MODELLED (TRUNC(OPT) and ARITH(EXTEND), det ports, a stop by name; INTDATE(LILIAN), det port, no oracle) / REFUSED (the rest) | NUMPROC: no; TRUNC(OPT): CBSA (det ports); ARITH(EXTEND): DBB EPSCSMRD (det ports) |
| C6 | compiler | COMP-1 / COMP-2: IBM hexadecimal floating point, and float-mode evaluation of the whole expression | MODELLED in the det runtime (HFP, #4271 slice 1); the oracle DIFFERS (IEEE, decimal evaluation): proven by IBM-cited vectors and on exact values; what the oracle cannot decide REFUSED by name | no (DBB EPSMPMT: its float `**` is an ASSUMED routine; the case waits on z/OS captures) |
| C7 | compiler | COMP-5 byte order: little-endian vs z/OS big-endian | DIFFERS; byte uses REFUSED by name in the det translator (#4271) | read as numbers only (a VALUE beyond the PICTURE: fixed, #4501) |
| C8 | compiler | DISPLAY of signed zoned, binary and packed items | MATCHED | yes |
| C9 | compiler | POINTER is 8 bytes in GnuCOBOL (x86-64), 4 on z/OS | DIFFERS (declared: each side's fields read by its own layout, compared by name; a POINTER only as NULL or not) | only NULL (CBSA, data after one included) |
| C10 | compiler | INITIALIZE / VALUE ZERO zoned items: unsigned F zone (GnuCOBOL) vs preferred C sign (z/OS) | DIFFERS (tolerated where a case declares it) | yes (CardDemo READACCT ARRYFILE) |
| C11 | compiler | A non-digit in a numeric DISPLAY item: MOVEd from an alphanumeric item (#4049); MOVEd to a binary item (#4652); read as a MOVE sender, an operand, a comparand, and the sign rewrite of a signed sender (#4662) | DIFFERS (#4049: inputs kept out of the cases) / MODELLED, the oracle's rules (#4652, #4662) | yes (COMEN01C option `1!`; GenApp LGTESTP4's add) |
| C12 | compiler | FUNCTION RANDOM: the oracle's generator (glibc via GnuCOBOL), not IBM's unpublished one; a seed IBM does not allow refused | DIFFERS (the numbers) / ASSUMED (the interface) | yes (CBSA CRDTAGY1-5, INQCUST: cbsa-crdtagy1..5, cbsa-inqcust, seeds 0 and a stated `"taskn"`; BANKDATA: cbsa-bankdata, seed 7, with an indexed file and Db2); translated, no proof yet (GenApp LGICVS01) |
| C13 | compiler | A numeric operand compared with a nonnumeric one (an alphanumeric, alphabetic or numeric-edited item): compared as its characters, not by value (#4665) | MATCHED (unsigned integer literals as written; zoned items as their digits, sign dropped; non-integer ones as the oracle's digits) / REFUSED (a signed literal, a SIGN SEPARATE, P-scaled, packed or binary item, an arithmetic expression, an equality with a literal of more decimal places than an edited item) | yes: CardDemo COTRTLIC (proven; an alphanumeric item against `0`); no proven program compares an edited item or a group with a number |
| C14 | compiler | Size errors without ON SIZE ERROR: a zero divisor leaves the receivers unchanged in the oracle (libcob's NaN), the det runtime the same (#4655); z/OS's result is undefined (a decimal-divide exception); 0 ** a negative is 0 in the oracle, a size error on z/OS | MATCHED (det runtime = oracle) / DIFFERS (oracle vs z/OS) | not known to be: no proven scenario divides by zero |
| C15 | compiler | `CALL identifier`: the port dispatches over the program names the item can hold, found from the source (VALUE, VALUE table, MOVEs of literals); uppercase names of up to 8 characters; any other value, write or name refused by name (#4736) | MODELLED where the names are known, REFUSED where they are not | yes (end-to-end test against cobc; DBB EPSCSMRT translates whole, its callee EPSMPMT is refused) |
| C16 | compiler | A 1- or 2-digit COMP-5 item: one byte in GnuCOBOL, a halfword on z/OS (and in the det layout), so offsets, record lengths and a value past the byte differ; no cobc option changes it (#4751) | DIFFERS (oracle vs IBM, declared) / REFUSED (the oracle refuses such a program by name) | no: no corpus or case declares one |
| C17 | compiler | INITIALIZE REPLACING of a table holding an item of a category REPLACING does not name: GnuCOBOL gives that item the first occurrence's value, IBM leaves it as it is; the port stops by name when the occurrences differ | DIFFERS (oracle vs IBM) / GUARDED (the port stops by name at run time when the occurrences differ) | yes: CardDemo COPAUA0C 8400-UPDATE-SUMMARY (PA-ACCOUNT-STATUS X(02) OCCURS 5, REPLACING NUMERIC); CODATE01 has no table |
| C18 | compiler | STORAGE, TRAP, ABTERMENC; Db2 DATE / TIME / DEC / DECPT / CCSID / bind options; CICS region and program-definition options: refuse, declare or no effect | DECLARED / REFUSED by name (LE, Db2 and CICS runtime options) | yes: every burned estate's recorded value resolves (STORAGE default via L3; GenApp EBCDIC CCSID 285 is declared) |
| C19 | compiler | ALTER p TO [PROCEED TO] q: the GO TO of p goes to q until the next ALTER of p; the port keeps the target in a slot the paragraph dispatcher reads | MODELLED where the paragraph is a lone GO TO, REFUSED otherwise (#5560) | yes (ALTER1 / ALTER2 in test_det_programs.py against GnuCOBOL -std=ibm; CardDemo CBSTM03A, 9 -> 5 holes) |
| D1 | data | Text order is ASCII (Latin-1), not EBCDIC | DIFFERS | keys: no; comparisons: not audited |
| D2 | data | Hex literals that name EBCDIC characters (`X'40'`); a hex literal is its raw bytes under every single-byte record charset (refused by name in a multi-byte one where it is not text), the SYSOUT record separator a plain LF (#4698) | DIFFERS (oracle vs IBM, characters) / MATCHED (the bytes, the oracle = the port = IBM) | yes (batch Sysout byte test, 4 record charsets, X'00'..X'FF' against cobc) |
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
| X6 | CICS | WRITEQ with a LENGTH past its FROM item (GenApp LGSTSQ): the record is FROM's bytes then SPACES to LENGTH on both sides (owner decision 2026-10-21); IBM writes the storage that follows, undefined (#4050) | ASSUMED (a LENGTH over 32767 REFUSED) | yes (GenApp LGACDB01, LGACDB02, LGDPDB01, LGIPDB01, LGUCDB01 error paths) |
| X7 | CICS | ASSIGN INVOKINGPROG / PROGRAM; LINKed programs run in one task | MATCHED | yes (GenApp LGUPDB01) |
| X8 | compiler | A reference modification past its item (no SSRANGE): a storage overlay | REFUSED | no |
| X9 | CICS | Named counters (GET COUNTER) | MATCHED | yes (GenApp LGACDB01) |
| X10 | CICS | A LINK target's COMMAREA bytes past the end of the caller's record | DIFFERS | no |
| X11 | CICS | ASKTIME ABSTIME into a field narrower than S9(15) COMP-3 (GenApp's WS-ABSTIME) | DIFFERS | yes (GenApp error paths, #4173) |
| X12 | CICS | A task with no COMMAREA that MOVEs DFHCOMMAREA anyway | UNDEFINED, masked | yes (DBB EPSCMORT) |
| X13 | CICS | An ESDS browsed by RBA: fixed-length records, a record's RBA its byte offset; RBAs that address no record refused | ASSUMED (REFUSED where IBM is silent) | yes (DBB EPSMLIST) |
| X14 | CICS | READ ... INTO LENGTH: in-out, truncation and LENGERR; a VSAM file's LENGTH need not equal its record length; LENGERR on READ UPDATE refused | ASSUMED (REFUSED where IBM is silent) | yes, NORMAL only (GenApp LGUCVS01 / LGUPVS01) |
| X15 | CICS | Terminal RECEIVE (INTO / SET, LENGTH, MAXLENGTH, NOTRUNCATE; LENGERR, EOC on an LUTYPE2 terminal) and SEND CONTROL | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-terminal-receive, hc-terminal-eoc) |
| X16 | CICS | HANDLE AID, IGNORE CONDITION, PUSH / POP HANDLE and HANDLE CONDITION ERROR on the det port | MATCHED (REFUSED where IBM is silent) | yes (cics-crucible hc-handle-aid, hc-ignore-error, hc-eoc-error) |
| X17 | CICS | Channels and containers: PUT / GET / DELETE CONTAINER, LINK / XCTL / RETURN CHANNEL (RETURN: the det port and the stub, carried to the next terminal task), ASSIGN CHANNEL; CHAR containers convert between CCSIDs 37, 500, 1140 and 1208 (ASCII bytes only) (FROMCCSID / INTOCCSID / CONVERTST / CCSID); GET CONTAINER BYTEOFFSET and PUT CONTAINER PREPEND on BIT containers; BYTEOFFSET / PREPEND on CHAR containers, other CCSIDs and multibyte 1208 refused GET64 / PUT64 CONTAINER as GET / PUT with INTO / FROM an ordinary item (GET64 SET refused); MOVE and the browse: X42; DELETE CHANNEL and QUERY CHANNEL: X44) | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible ca-channel-containers, pinned at v0.10.0) |
| X18 | CICS | Interval control on the det port: START (INTERVAL / TIME / AFTER / AT, TERMID, REQID, PROTECT, FROM, RTRANSID / RTERMID / QUEUE, CHANNEL), RETRIEVE (INTO / LENGTH, the data options, ENVDEFERR), CANCEL REQID, RUN TRANSID CHILD [CHANNEL], FETCH ANY / CHILD (NOSUSPEND, TIMEOUT or waiting), FREE CHILD, and DELAY as the wait that dispatches RUN children (#4950); the child schedule, TIME RESP2 and the order of out-of-range checks assumed; ties, a child's region-resource commands, RETRIEVE SET / WAIT refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible gt-start-retrieve, gt-terminal-coalesce, gt-start-options, pinned at v0.10.0) |
| X19 | CICS | ASSIGN on the det port: STARTCODE (TD / S / SD / D), USERID (the default user), FACILITY / SCRNHT / SCRNWD (INVREQ RESP2 5 without a terminal) from facts the harness states; no data area written when ASSIGN raises INVREQ; OPID, NETNAME, TERMCODE, FCI, the other screen sizes, work-area lengths and the rest refused | ASSUMED (REFUSED where the harness cannot decide) | yes (cics-crucible gt-assign-startcode, pinned at v0.10.0) |
| X20 | CICS | SEND TEXT on the det port and the stub: TERMINAL accepted as the default output disposition (the principal facility; the event is that of SEND TEXT without it); ACCUM, PAGING, SET, REQID, HEADER, TRAILER, JUSTIFY / JUSFIRST / JUSLAST, the printer, partition and LDC options, MSR, FMHPARM, DEFAULT / ALTERNATE refused | MATCHED (REFUSED where the region cannot decide) | yes (cics-crucible gt-send-text-terminal, unreleased) |
| X21 | CICS | EIBTASKN: the task's number is a stated fact of the run (`$GGCICS_TASKN` / `CicsTask.withTaskNumber`, a case's or scenario's `"taskn"`, default 0), not the number CICS assigns; a value outside 0 to 9,999,999 refused | DIFFERS (the value) / MATCHED (both sides) | yes (every CICS task; read by CBSA's Db2 programs, GenApp LGICDB01) |
| X22 | CICS | READ GTEQ / GENERIC on a KSDS: the first record whose key (or its first KEYLENGTH bytes) equals RIDFLD's or, with GTEQ, is greater, in the browse's key order (D1); NOTFND RESP2 80; READ UPDATE holds the record found; RIDFLD not updated; #4771: on a file named at run time the full key is that file's (looked up then), and DELETE GENERIC deletes every record with the generic key (NOTFND RESP2 80 when none); DELETE INVREQ RESP2 21 (ESDS), 22 (generic on a non-KSDS), 25 / 42 (GENERIC KEYLENGTH not shorter than the key / below zero) and 26 (KEYLENGTH without GENERIC) on both runtimes (#5092, as READ's: X52); refused: a GENERIC KEYLENGTH of zero, a non-constant KEYLENGTH and a RIDFLD shorter than the key searched | ASSUMED (REFUSED where IBM is silent or the layout decides) | yes (GenApp LGICVS01 genapp-lgicvs01) |
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
| X35 | CICS | The HTTP server is a stated fact (http_peers: scheme, host, port, CLIENT URIMAP and path, and the response to each request, matched by method, path and query in order); WEB OPEN by URIMAP or HOST / HOSTLENGTH / PORTNUMBER (80 / 443 when omitted) / SCHEME returns our 8-byte token (GGWSnnnn), LENGERR 21, INVREQ 40 / 138; WEB CONVERSE sends METHOD, PATH (the URIMAP's when omitted), QUERYSTRING, FROM with MEDIATYPE, recorded as a WEB-CONVERSE event, and returns INTO (at most MAXLENGTH, INTO's length when omitted; LENGERR 57 when longer), TOLENGTH, STATUSCODE, the reason phrase's bytes and MEDIATYPE (blank-padded to 56), with NOTOPEN 27, INVREQ 33 / 34 / 54 / 76, LENGERR 5 / 8 / 16 / 50 / 59; WEB CLOSE NOTOPEN 27; the exchange is in the program's characters (conversion options change nothing); refused: an unstated peer or response, two conditions at once, TRACE / OPTIONS, MAXLENGTH 0, no PATH on a HOST session, a blank MEDIATYPE with a body, a reason phrase longer than STATUSLEN, a length past its area, and every option zECS does not use | ASSUMED (REFUSED where IBM is silent) | partly (unit-proven on CicsTask and the stub C, which answer one step list alike; the cics-crucible `gt-web-client` case is a ledger row at the v0.10.0 pin (#6230): both cobol-stub cells pass; since #6457 the committed det port of GTWCLI also passes java-ported and java-facade on both scenarios, re-run 2026-10-24: cobol-stub, java-ported and java-facade each 2 of 2 on the one expected log; only the bare `java` side, the generated skeleton, fails) |
| X36 | CICS | WEB PARSE URL is pure: URL / URLLENGTH are split into SCHEMENAME (upper case, blank-padded to its 16-byte area), HOST / HOSTLENGTH, PORTNUMBER (explicit, else 80 for HTTP and 443 for HTTPS), PATH / PATHLENGTH (with its leading slash) and QUERYSTRING / QUERYSTRLEN (without its question mark, still escaped); each length option is read as the area's size and set to the piece's length; INVREQ 28 (no scheme and ://, an empty scheme or host, a port that is not 1-5 digits or above 65535: ASSUMED) and INVREQ 65 (a percent not followed by two of 0-9 A-F); the areas are written on NORMAL only; an IPv6 host is written in brackets and returned without them (IBM, per the crucible's gt-web-parse-url); LENGERR RESP2 29 / 30 / 8 (host / path / query string longer than its length) with the areas and lengths left alone (ASSUMED); refused: a scheme other than HTTP / HTTPS, user-info, a fragment, an IPv6 host that is not [hex:colons] or [hex:colons]:port, an empty port or port 0, a lowercase hex digit in an escape, a URLLENGTH not above zero or past its area, a length past its area, a PATH or QUERYSTRING asked for when the URL has none, two conditions at once (INVREQ and LENGERR, or two pieces too long), HOSTTYPE | ASSUMED (REFUSED where IBM is silent) | cobol-stub passes gt-web-parse-url (parse, errors, lengerr); unit-proven on CicsTask and the stub C, which answer one step list alike |
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
| X47 | CICS | A USAGE POINTER item holds the handle of a block of task storage; GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(byte) acquires one (every byte the INITIMG value; LENGERR RESP2 1 for FLENGTH below 1 or LENGTH zero, the pointer then zero), FREEMAIN DATAPOINTER(ptr) releases it (INVREQ RESP2 1 for an address GETMAIN did not return: a null pointer, a record's address), WEB RECEIVE SET(ptr) LENGTH(area) [MAXLENGTH] puts the request body in a new block (MAXLENGTH optional: all of it; LENGERR RESP2 16 leaves the pointer as it was, RESP2 57 cuts the body and sets it), SET ADDRESS OF record TO pointer / TO ADDRESS OF record makes a LINKAGE 01 record's bytes the block's (a real alias), SET ADDRESS OF record TO ADDRESS OF item (a subordinate item or a WORKING-STORAGE record) makes the record a window onto that item's bytes (Storage.base), SET pointer TO ADDRESS OF record / item gives its handle (block plus offset); refused: GETMAIN without INITIMG, a literal INITIMG, SHARED, NOSUSPEND, FREEMAIN DATA, a length above 256 MiB (LENGTH above 65520), a second FREEMAIN of the same block, FREEMAIN of a WEB RECEIVE SET body, SET ADDRESS OF a null / freed pointer, ADDRESS OF a table element, SET ADDRESS OF ... TO NULL, a pointer a REDEFINES overlays (pointer arithmetic) | ASSUMED (REFUSED where IBM is silent) | no (unit-proven: CicsTask and the stub C answer one list of steps alike, tests/cics_crucible/test_cics_runtimes.py _X47_CASES; DetCics's aliasing compiled and run, tests/cobol_mainframe/test_pointer_lane_4771.py; ZECS001 translates 560 of 561 statements through it, the pointer-lane and CALL ZUIDSTCK holes closed, ZUIDSTCK executed-equivalent on two stated TODs (zecs-zecs001); the COMMAREA DTO the stub does not carry is the one left) |
| X48 | CICS | The equivalence harness's `faults` take DUPKEY (RESP 15, RESP2 140) on READ / READNEXT / READPREV, where the read runs and delivers its record (INTO, and RIDFLD for a browse, and a READ UPDATE's hold) and answers DUPKEY; DUPREC (14, RESP2 150) on WRITE / REWRITE, where nothing is written; any other command / condition pair of the two, a wrong RESP2, and DUPKEY on DELETE are refused by name | ASSUMED (REFUSED where IBM is silent) | no (the reference region has no alternate index path to read through; proved on both sides by the stub (tests/equivalence/cics/ggcics.c) and CicsTask.withFaults against each other: tests/cobol_mainframe/test_equivalence_cics.py, tests/cics_crucible/test_cics_runtimes.py) |
| X49 | CICS | The equivalence harness's `faults` on a file command (READ, READNEXT, READPREV, STARTBR, ENDBR, WRITE, REWRITE, DELETE) take a condition only where IBM lists it for that command, and carry IBM's RESP2 (given, or the default when IBM gives one; INVREQ and LENGERR have several, so the scenario names one); an unlisted command / condition pair, a RESP2 IBM does not give, the data-table and RLS conditions (LOADING, RECORDBUSY, CHANGED, SUPPRESSED) and ILLOGIC on READNEXT / READPREV / REWRITE (IBM also ends the browse, not modelled) are refused by name | ASSUMED (REFUSED where IBM is silent) | no (an injection: the reference region's logs do not hold these conditions; the planned form is proved on both sides by the stub (tests/equivalence/cics/ggcics.c) and CicsTask.withFaults reading the same plan: tests/cics_crucible/test_file_fault_conditions.py, tests/cobol_mainframe/test_equivalence_cics.py) |
| X50 | CICS | A fullword counter has the limits DEFINE COUNTER gave it (MINIMUM zero and MAXIMUM X'7FFFFFFF' when omitted; VALUE zero; INVREQ RESP2 407 for MAXIMUM below MINIMUM or beyond X'7FFFFFFF', 406 for VALUE below MINIMUM or above MAXIMUM + 1); GET COUNTER at MAXIMUM + 1 is SUPPRESSED RESP2 101 and leaves the counter, or with WRAP returns MINIMUM and goes on from it; QUERY COUNTER returns VALUE / MINIMUM / MAXIMUM; an INCREMENT beyond MAXIMUM - MINIMUM or past MAXIMUM + 1, a VALUE or MINIMUM below zero, and the limits of a counter whose limits the run does not state are refused | ASSUMED (REFUSED where IBM is silent) | no |
| X51 | CICS | EXEC CICS RETURN TRANSID COMMAREA LENGTH and XCTL COMMAREA LENGTH hand the next task / the target LENGTH bytes (its EIBCALEN), every byte as it was; the det port passes the record's whole span beside its DTO (#4806, #4817), so CicsTask cuts those bytes at LENGTH (null: all; past the span: all of it), as the DTO's reading already is; a LINK's area is not cut (by address); a LENGTH past the DTO passes the COMMAREA as a byte[] (region EBCDIC), which a det facade's handleTransaction answers as the program's own DTO, read through its layout in the port's page (#4695; the task keeps the bytes) | ASSUMED | no (unit-proven on CicsTask for RETURN, RETURN IMMEDIATE and XCTL, every LENGTH class: tests/cobol_mainframe/test_commarea_length_bytes_4817.py; reached by CBSA BNK1UAC, BNK1TFN and BNK1CCS (#5089: RETURN LENGTH differs from the record; det_port.py run PROVED, java-facade answered; the other burned RETURN sites, CBSA BNK1CCA/CRA/DAC/CAC/DCS/BNKMENU and DBB EPSCMORT, also PROVED); a conforming program never reads past EIBCALEN) |
| X52 | CICS | READ NOTFND RESP2 80 and INVREQ 25 / 26 / 42 for a KEYLENGTH (#5092), READ UPDATE TOKEN(d) returns a fullword token for the record held; REWRITE / DELETE / UNLOCK TOKEN(t) act on that record, and a token that matches none in use (never issued, spent, another file's) is INVREQ RESP2 47; a SYNCPOINT ends every token. The token's value is ASSUMED (the task's 1, 2, 3, ...). Refused: READNEXT / READPREV UPDATE [TOKEN] (RLS only), DELETE TOKEN with RIDFLD or GENERIC, REWRITE TOKEN whose FROM has another key | ASSUMED (REFUSED where IBM is silent) | unit-proven on CicsTask and the stub C over one scenario list (tests/cics_crucible/test_update_token_runtimes_5078.py: valid, invalid, reused, interleaved, wrong-file tokens; test_unlock_held_5079.py: UNLOCK without TOKEN); CBSA DELCUS (READ UPDATE TOKEN twice, DELETE TOKEN twice) translates whole (det_survey: 140 of 140 statements, compiles) |
| X53 | CICS | REWIND resets a counter that has reached its limit (MAXIMUM + 1) to its minimum, else SUPPRESSED RESP2 102, INVREQ 406 for an INCREMENT beyond (maximum - minimum) + 1; UPDATE sets the current value (INVREQ 406 below MINIMUM or above MAXIMUM + 1); GET REDUCE leaves a counter an INCREMENT would carry past MAXIMUM + 1 at MAXIMUM + 1, GET COMPAREMIN / COMPAREMAX hand the value out only when it is in range (either bound when COMPAREMAX is below COMPAREMIN), else SUPPRESSED RESP2 103 and the counter stays; NOSUSPEND is accepted and changes nothing (one task, no coupling-facility structure, so BUSY RESP2 500 cannot occur). Refused: UPDATE COMPAREMIN / COMPAREMAX, REWIND INCREMENT above 1, REDUCE with WRAP or at a counter already at its limit, COMPARE at a counter already at its limit, a negative VALUE / compare value of a fullword counter, REWIND / UPDATE of a counter whose limits the run does not state | ASSUMED (REFUSED where IBM is silent) | no |
| X54 | CICS | A DFHMDF field coded JUSTIFY=(RIGHT[,ZERO]) / (LEFT,ZERO) receives the operator's input right- or left-justified and filled with zeros or blanks, as BMS does; <f>L stays the length of the text typed. A field with no JUSTIFY is left-justified and blank padded, except a NUM field: RIGHT,ZERO (#5116) | ASSUMED (where IBM is silent) | unit-proven on DetJustify.place over the whole operand class (tests/cobol_mainframe/test_det_receive_map_justify_5082.py); PCCONF (pc-wizard) RECEIVE MAP into a JUSTIFY=(RIGHT,ZERO) field |
| X55 | CICS | A program written to CICS's macro-level API (DFHPC / DFHFC / DFHTC / DFHSC ... TYPE= macro calls, CSA / TCA addressing) or an assembler program written for CICS (DFHEIENT / DFHEISTG / EXEC CICS in HLASM) is its own refusal family: the scanner names it, the support matrix and blocker report count it per estate, and the det translator refuses it with the reason instead of reading it as COBOL with holes | REFUSED | no (no burned estate holds one; unit-proven on gitgalaxy/core/cics_macro_level.py and the det source check) |
| X56 | CICS | An OS/VS COBOL program's BLL cell list (the LINKAGE 01 of fullwords after DFHCOMMAREA, a FILLER first, one cell per 4096 bytes of each following 01) is rewritten before translation as IBM's 'Converting to VS COBOL II' says: the cells become POINTERs (X47), SET(cell) stays SET(pointer), SERVICE RELOAD record becomes SET ADDRESS OF record TO its cell, a long record's ADD 4096 secondary cells go, MOVE cell TO cell is SET; the det port and the GnuCOBOL oracle run that one program. IBM's chained storage areas are kept: a record whose cell changes with no SERVICE RELOAD later in its paragraph is addressed again through its cell at every paragraph name, and an address moved between a cell and a fullword of data is a token both runtimes number alike (ASSUMED). MOVE ZERO / LOW-VALUES TO a cell is SET cell TO NULL (the all-zero handle, as X47; ASSUMED: IBM's book is silent on clearing a cell, its conversion makes the cell a POINTER). Every SET(cell) read command is its SET(pointer) form (X58). Refused whole by name (OS/VS COBOL BLL addressing: ...): a cell used as a number or moved to / from data that is no plain fullword, a reload or a paragraph name before a long record's secondary cells are reset, DECLARATIVES in a program whose records are addressed again at paragraph names, a secondary cell set any other way than ADD 4096, a cell as a command's data, SERVICE LABEL, SERVICE RELOAD of a non-LINKAGE item or of a record no cell addresses, DFHCOMMAREA after the list, a list in a COPY member | ASSUMED (REFUSED where IBM is silent) | yes, on a synthetic estate only (tests/cobol_mainframe/test_bll_cells_5119.py: a long record over two cells and a record aliased to it, a three-area chain walked through NEXTAREA and a paragraph name, and READQ TS SET(cell), each proven against GnuCOBOL end to end, and a three-cell 8200-byte record with a cell moved, cleared and tested against ZERO (BLLNULL); the cell count per record tested at 4095/4096/4097/8192/8193 bytes and under OCCURS; every SET(cell) command and every refusal tested; the tokens' step lists answered alike by CicsTask and the stub, tests/cics_crucible/test_bll_tokens_5119.py). No corpus program uses BLL cells; estate-crucible's era strata (#5118 S4-S6) are to carry the corpus cases |
| X57 | CICS | READQ TD QUEUE INTO [LENGTH]: a destructive, first-in first-out read of the queue the task's own WRITEQ TDs fill; QZERO for an empty queue, QIDERR for a queue the CSD does not define, LENGERR (the record read and lost, INTO holding its first LENGTH bytes) for a record longer than LENGTH or a LENGTH of zero, LENGERR with nothing read for a negative LENGTH, LENGTH set to the record's own length. DELETEQ TD: every record of an intrapartition queue; QIDERR; INVREQ for an extrapartition queue. (Since #5168, X61 models extrapartition queues, SET, NOSUSPEND, INDIRECT and LOGICAL recovery.) Refused by name in X57: READQ TD of an extrapartition queue (and of any queue whose CSD TYPE is neither INTRA nor EXTRA), READQ TD SET / SYSID / NOSUSPEND, DELETEQ TD SYSID and of a queue with a TYPE other than INTRA / EXTRA, a record moved past INTO. The WRITEQ TD event keeps its shape | ASSUMED (REFUSED where IBM is silent) | no corpus program issues either command yet; proven on both runtimes with hand-traced operation lists (tests/cics_crucible/test_td_queue_5079.py) and the translator's refusals (tests/cobol_mainframe/test_equivalence_cics.py) |
| X58 | CICS | Each command, given SET(pointer-item) where it used to take INTO, puts a copy of the data in a new block of task storage and the block's handle in the pointer (the pointer lane of X47); SET ADDRESS OF a LINKAGE 01 record then reads it. LENGTH / FLENGTH is the data's length. The pointer ends where IBM says: RECEIVE and READQ TS at the next command of the kind, GET CONTAINER at the next GET CONTAINER SET of the same container or its DELETE / MOVE / the channel's DELETE, READ at the next READ of the file or a REWRITE / DELETE / UNLOCK (a READ UPDATE SET also at SYNCPOINT), READNEXT / READPREV at the next SET of the browse, its ENDBR or a SYNCPOINT; RETRIEVE states no end (to the task's end, ASSUMED). An ended pointer's storage reads as zeros (ASSUMED). A condition that delivers no data leaves the pointer as it was (ASSUMED). Refused by name: SET with INTO, a missing or literal LENGTH where IBM requires a data area, RBA / RRN / XRBA, a LENGTH on a browse SET, BYTEOFFSET, FREEMAIN of any of these blocks, a PUT or MOVE CONTAINER onto a container whose GET CONTAINER SET pointer is held; SEND MAP / RECEIVE MAP / SEND CONTROL SET (BMS storage) and LOAD SET, GETMAIN64 / FREEMAIN64 stay refused | ASSUMED (REFUSED where IBM is silent) | no (unit-proven: the stub and CicsTask answer one list of 37 step lists alike, tests/cics_crucible/test_cics_set_pointer_5042.py; the translators' shapes and refusals and a compiled DetCics run, tests/cobol_mainframe/test_pointer_lane_5042.py; no estate program translates whole through one of these yet) |
| X59 | CICS | EXEC CICS ADDRESS EIB(ptr) and COMMAREA(ptr) set a pointer to the task's own EIB / DFHCOMMAREA record (the pointer lane of X47): a LINKAGE record set to the pointer shares the bytes, so the EIB's later updates and a write through the COMMAREA view show in both. The command has no condition (NORMAL). A task with no COMMAREA (EIBCALEN 0) is refused when it runs: IBM sets the pointer to X'FF000000', which is not the COBOL NULL a pointer handle can hold. Refused by name: ADDRESS CWA, TWA, TCTUA and ACEE (system areas the region does not define), the old ADDRESS SET form, ADDRESS COMMAREA in a program with no 01 DFHCOMMAREA, and the old-style sweep: SEND PAGE and PURGE MESSAGE (a BMS logical message); CONVERSE, POST and WAIT EVENT are modelled by X63 | ASSUMED (REFUSED where IBM is silent) | no corpus program issues them yet; proven end to end on GnuCOBOL with the stub and on the det port with a hand-traced program (tests/cobol_mainframe/test_address_e2e_5079.py), the translators' shapes and refusals and both runtimes' no-COMMAREA refusal (tests/cobol_mainframe/test_address_5079.py) |
| X60 | CICS | A scenario can plan ENQBUSY (RESP 55) for an ENQ by the RESOURCE operand as the program writes it; RESP2 is 0 because IBM states none for ENQBUSY. The ENQ must say NOSUSPEND: without it IBM suspends the task and the runtimes refuse. ENQ's other conditions come from the program's own operands, never from a plan: LENGTH outside 1 through 255 is LENGERR RESP2 1 and a MAXLIFETIME that is neither UOW nor TASK is INVREQ RESP2 2 (both modelled, as IBM states them). Refused: ENQBUSY planned for any other command, any other condition planned for ENQ, a RESP2 on an ENQBUSY plan, a planned-busy ENQ without NOSUSPEND, a resource that is no data-name of 1 to 16 characters, both bad operands at once (IBM names no order) | ASSUMED (REFUSED where IBM is silent) | no |
| X61 | CICS | READQ TD SET(ptr) LENGTH(data-area) puts the record in a new block valid to the next READQ TD (X58's pointer lane), LENGTH the record's length; NOSUSPEND is accepted; on a LOGICAL intrapartition queue holding no record it answers the QBUSY a scenario plans (round 9). An extrapartition queue (TYPE EXTRA) answers by its definition: OPENTIME(DEFERRED) is closed, so NOTOPEN (19); TYPEFILE(OUTPUT) open, INVREQ (16); TYPEFILE(INPUT) open reads its records first in first out, QZERO at the end. A case seeds (text the data encoding holds whole, non-ASCII included) the records of an intrapartition queue or an input data set ("td"). WRITEQ TD to an extrapartition queue: INVREQ (16) when it is open for input, NOTOPEN (19) when closed (#5168 round 2). RECOVSTATUS(LOGICAL): SYNCPOINT ROLLBACK, or a task's abend, puts the queue back as it was at the last SYNCPOINT (reads, writes and DELETEQ alike); NO commits at once. An INDIRECT queue routes READQ / WRITEQ / DELETEQ to its INDIRECTNAME, itself possibly indirect. Refused by name: SYSID and REMOTE queues, IOERR (no data set), RDBACK or no TYPEFILE, RECOVSTATUS(PHYSICAL) with a SYNCPOINT ROLLBACK, a WRITEQ TD that brings a queue with a TRANSID to its TRIGGERLEVEL (automatic task initiation), an INDIRECT queue with no INDIRECTNAME / an undefined target / a loop, a SYNCPOINT ROLLBACK after a SYNCPOINT (CicsTask). SET TDQUEUE(q) OPENSTATUS(OPEN | CLOSED) opens or closes an extrapartition queue at run time (the state replaces OPENTIME and outlives the task) and INQUIRE TDQUEUE(q) OPENSTATUS / TYPE reads them (#5168 round 3): QIDERR RESP2 1, INVREQ RESP2 8 (invalid CVDA) and 9 (intrapartition queue); every other SET / INQUIRE TDQUEUE option, an INDIRECT or REMOTE queue, OPEN with no TYPEFILE, OPEN of an input queue already read, and an invalid CVDA on a queue that is not extrapartition are refused by name The messaging forge's RoutingTransientData follows the same definitions (#5168 round 4): INDIRECT chains, NOTOPEN for a closed extrapartition queue, input data sets read first in first out, INVREQ for the wrong direction and for DELETEQ, SYSID / REMOTE and broken chains refused by name | ASSUMED (REFUSED where IBM is silent) | no corpus program issues these forms yet (2026-10-19: a case-insensitive grep for READQ TD over the six burned estates, CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication and the cicsdev async credit-card repo, finds no READQ TD at all, so READQ TD SET has no burned-estate program to prove against; 2026-10-23, same six estates: no TRIGGERLEVEL, TRANSID-bearing or ATI option anywhere, no SYSID on any TD command, and the only TDQUEUE definition is CardDemo's JOBS (TYPE EXTRA, TYPEFILE OUTPUT, modelled), so automatic task initiation and remote SYSID / REMOTE queues have no burned program to prove against and stay refused by name; its end-to-end proof is the synthetic program, GnuCOBOL leg run with EQUIVALENCE_E2E=1); proven on both runtimes with hand-traced operation lists (tests/cics_crucible/test_td_queue_5168.py, 17 scenarios), the translators' shapes and refusals (tests/cobol_mainframe/test_equivalence_cics.py, test_det_translate.py) and end to end against GnuCOBOL (tests/cobol_mainframe/test_td_queue_e2e_5168.py, test_td_openstatus_e2e_5168.py); round 3: 35 scenarios in the same file and tests/cobol_mainframe/test_td_openstatus_translate_5168.py |
| X62 | CICS | The resource map is built from definition sources in the repository (CSD decks, assembled macro tables, including tables in JCL assembler SYSIN). What a running region installed, enabled or changed through CEDA, CEMT or EXEC CICS SET / CSD commands is not in a source tree, so no scan can state it; the map names that limit instead of guessing | REFUSED | no (a static property: nothing to reach) |
| X63 | CICS | EXEC CICS POST makes a 4-byte timer-event control area (binary zeros) and, with SET, hands its address to the program; WAIT EVENT ECADDR waits for it and the area is then posted (first byte X'40', third byte X'80'). A task takes no time (X4), so the area is posted only by a WAIT EVENT, which runs the stated clock to the expiry, or by a CANCEL of the POST. POST raises INVREQ (RESP2 4 / 5 / 6) and EXPIRED, WAIT EVENT INVREQ RESP2 2. CONVERSE (default) writes FROM to the terminal and reads the reply INTO, TOLENGTH set, LENGERR for a longer reply. Refused by name: a WAIT on an area a later POST, CANCEL, START or DELAY ended, an ECB that is no POST's, CONVERSE on an LUTYPE2 terminal and CONVERSE SET / the conversation options | ASSUMED (REFUSED where IBM is silent) | no corpus program issues them (0 uses in the 18 corpora, #5079); proven end to end on GnuCOBOL with the stub and on the det port with a hand-traced program (tests/cobol_mainframe/test_post_wait_converse_e2e_5079.py), the translators' shapes, every option and refusal and both runtimes' conditions (tests/cobol_mainframe/test_post_wait_converse_5079.py) |
| X64 | CICS | EIBDS is the FILE / DATASET of the last file control request on both runtimes (before the request runs); EIBFN, EIBRCODE, EIBCPOSN, EIBREQID, EIBRSRCE, EIBERR and EIBERRCD are INITIALIZEd on both sides and stay `fact:` gaps in proof_blockers | ASSUMED (EIBDS) / REFUSED (the other EIB resource and response fields) | EIBDS: only ZECS001 reads it (a program with holes, no case yet); the others: ZECS001's EIBRCODE (the same program) |
| X65 | CICS | Every EXEC CICS command the det translator does not model is a hole named after the command, never a guess. This entry lists them by class with the reason: BTS (40 commands), APPC / DTP conversations (13) and GDS (14), batch data interchange ISSUE (13), security (12), terminal control beyond one 3270 display (11), SOAP / WS-Addressing (9), journals (5), JES spool (5), TRANSFORM (4), DOCUMENT INSERT / SET / DELETE (3), OpenTelemetry (3), 64-bit GET64 / PUT64 CONTAINER and GETMAIN64 / FREEMAIN64 (4), partitions (2), trace and monitoring (2), and LOAD and RELEASE (engine-only: the engine derives the edge, the translator refuses them), and single commands (SUSPEND, ISSUE PASS, ROUTE, ADDRESS SET, RESETBR, INVOKE APPLICATION, BIF DIGEST, CHANGE TASK, CONVERTTIME, INQUIRE CONTAINER). Each command's own reason is its entry in gitgalaxy/standards/cics/commands/api.py (the translator's hole message); X46 (DUMP TRANSACTION), X59 and X63 keep their own entries | REFUSED | no burned estate (CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication, async credit-card) uses any of them except SOAPFAULT CREATE in DBB MortgageApplication (web services, out of scope for #4270); test_cics_refusals_registered_4270.py pins that every refused command names a register entry that exists and test_cics_burned_reach_4270.py pins that every command a burned estate issues is modelled |
| X66 | CICS | SET TDQUEUE(q) ENABLESTATUS(ENABLED | DISABLED) makes a queue available or unavailable at run time, and INQUIRE TDQUEUE(q) ENABLESTATUS reads it back (ENABLED 23, DISABLED 24). A disabled queue answers DISABLED (84) to READQ TD, WRITEQ TD and DELETEQ TD, whatever its type or open state, and the command does nothing (a WRITEQ records no text). The state is kept across tasks and is not part of a unit of work (a SYNCPOINT ROLLBACK keeps it); a queue is ENABLED until a SET says otherwise. QIDERR RESP2 1 for a queue the CSD does not define, INVREQ RESP2 10 for an invalid CVDA. Refused by name: SET with OPENSTATUS and ENABLESTATUS together, SET ENABLESTATUS of an INDIRECT or REMOTE queue, an invalid CVDA on a queue the CSD does not define. Still refused (unchanged from X61): ATIFACILITY, ATITERMID, the INQUIRE browse, SYSID / REMOTE, IOERR, QBUSY | ASSUMED (REFUSED where IBM is silent) | no corpus program issues these forms; proven on both runtimes with hand-traced operation lists (tests/cics_crucible/test_td_queue_5168.py, the round 5 scenarios), the translators' shapes and refusals (tests/cobol_mainframe/test_td_enablestatus_translate_5168.py) and end to end against GnuCOBOL (tests/cobol_mainframe/test_td_enablestatus_e2e_5168.py) |
| X67 | CICS | EXEC CICS HANDLE ABEND PROGRAM(name) names a program that gets control when the task abends. The det translator honours LABEL, CANCEL and RESET and refuses PROGRAM by name with this entry; the cobol-stub refuses it too (equivalence_cics.Unsupported), so the two sides agree | REFUSED | no burned estate (CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication, async credit-card) issues HANDLE ABEND PROGRAM: they use LABEL (6), CANCEL (1) and LABEL with NOHANDLE (1); non-burned census programs are counted by tools only |
| X68 | CICS | EIBTRNID: the transaction id the task runs under is the case's `"transid"`, moved into EIBTRNID (PIC X(4)) on both sides; nothing validates it against a CSD or checks its length | ASSUMED (the value is the case's) / MATCHED (both sides) | yes (every CICS task; GenApp's LG* programs and CBSA's CRDTAGY1 / XFRFUN move it into a transaction-name field, zECS names it) |
| X69 | LE / CICS | ZUIDSTCK's 16 bytes are opaque; the program depends only on them being stated; their STCK/STCKE layout is not modelled. The port (cobolrt/le/Zuidstck.java) and the oracle (tests/equivalence/le/zuidstck.c) fill THE-TOD from the run's stated $GGC_ZUIDSTCK_TOD (32 hexadecimal digits, the harness's tod case key); an unstated, malformed or wrongly sized TOD is refused by name; the host clock is never read; every call of a run returns the same bytes | ASSUMED | yes (executed-equivalent: zecs-zecs001, 2 stated TODs, 0 diffs on every event and on the key record; the opaque-bytes assumption itself is not provable against z/OS) |
| X70 | CICS | A scenario can plan an abend on a file control command (READ, READNEXT, READPREV, STARTBR, ENDBR, WRITE, REWRITE, DELETE), or on a `LINK` (`{"cmd": "LINK", "program", "resp": "ABEND", "abcode"}`: the RLS abend of the linked program seen at its caller), with `{"cmd", "file", "nth", "resp": "ABEND", "abcode": "AFCR|AFCS|AFCT|AFCC"}`: the command raises no condition (RESP and RESP2 stay NORMAL, RESP and HANDLE CONDITION do not see it) and the task abends with that code, cause system; the nearest active HANDLE ABEND exit gets control (the levels below it are unwound), and without one the task ends with the unit of work backed out. Refused: any other abend code, any other command, a RESP2 named on the plan | ASSUMED (REFUSED where IBM is silent) | yes (CardDemo COCRDUPC, CBSA INQACCCU, CBSA INQCUST) |
| X71 | CICS | A scenario can plan a condition on SEND MAP (INVMPSZ, TSIOERR, INVREQ RESP2 200), RECEIVE MAP (INVMPSZ, INVREQ), SEND TEXT (TSIOERR, INVREQ RESP2 200, LENGERR), RETURN (INVREQ RESP2 1/2/4/200, LENGERR RESP2 11/26/27), SYNCPOINT and SYNCPOINT ROLLBACK (INVREQ RESP2 200) with `{"cmd": "SEND-MAP|SEND-TEXT|RECEIVE-MAP|RETURN|SYNCPOINT|ROLLBACK", "map": "..", "nth": n, "resp": "..", "resp2": n}`. The command is not performed, RESP / RESP2 / EIBRESP carry the plan, and HANDLE CONDITION fires when the command codes no RESP. Refused: every other condition IBM lists for these commands (device, partition, paging, remote-system and PLT conditions, ROLLEDBACK), a RESP2 where IBM states none, a RESP2 outside IBM's list | ASSUMED (REFUSED where IBM is silent) | yes (CBSA BNKMENU, DBCRFUN, BNK1UAC, BNK1CRA, BNK1CAC, BNK1CCA, BNK1CCS, BNK1DAC, BNK1TFN) |
| X72 | CICS | A scenario can plan a failed DELAY with `{"cmd": "DELAY", "nth": n, "resp": "EXPIRED|INVREQ", "resp2": n}` (INVREQ RESP2 4, 5, 6 or 22; EXPIRED names none). The delay is not performed (no child task is dispatched, the clock does not move, no POST is released), RESP / RESP2 / EIBRESP carry the plan, and HANDLE CONDITION fires when the command codes no RESP. Refused: NORMAL RESP2 23 (the delay cancelled by another task, which needs a second task), every other condition, a RESP2 where IBM states none, a RESP2 outside IBM's list | ASSUMED (REFUSED where IBM is silent) | yes (CBSA CRDTAGY1-5) |
| X73 | CICS | A scenario `sql_faults` entry that names its statement by `line` and fails it with SQLCODE -911 can add `"abend": "AD2Z"`: the statement fails as planned (SQLCODE -911, SQLSTATE 40001, set in the SQLCA) and the task then abends AD2Z, cause system; the nearest active HANDLE ABEND exit gets control (`ASSIGN ABCODE` reads AD2Z), and without one the task ends with the unit of work backed out. AD2R and AD2X (the attach's other task abends, below) may be planned the same way on any SQLCODE. Refused: any other abend code, any SQLCODE but -911 for AD2Z, a statement selected by table and verb, a program with no HANDLE ABEND | ASSUMED (REFUSED where IBM is silent) | yes (CBSA DBCRFUN, XFRFUN, INQACCCU) |
| L1 | LE | CEEDAYS: numeric date pictures (YYYY MM DD in any order, YYYY DDD) read as their span; date characters past the span ignored (documented), an all-blank picture tail ignored (assumed), the slack past a picture item blank (assumed, CRECUST), a non-blank tail refused; open conditions refused by name | MATCHED / ASSUMED / REFUSED | yes (CardDemo carddemo-dateutil; CBSA cbsa-crecust, cbsa-bnk1ccs, #4952, #5089) |
| L2 | LE | CEE3ABD abend codes | MATCHED | yes |
| L3 | LE | WORKING-STORAGE with no VALUE clause: GnuCOBOL's spaces vs LE's STORAGE option on z/OS | ASSUMED | yes (CardDemo READACCT OUTFILE, 2 bytes; CBSA CRDTAGY1-5 container-short, WS-CONT-IN past a short container) |
| L4 | LE | CEEIGZCT: a stand-in declaring the symbolic feedback code CEE000 only (CBSA CRECUST, #4884) | ASSUMED | yes (cbsa-crecust, #4952) |
| L5 | LE | CEELOCT: Lilian day, seconds and YYYYMMDDHHMISS999 from the pinned clock, feedback all zero; the unwritten tail of IBM's longer Gregorian field and the float's representation assumed | ASSUMED | yes (CBSA CRECUST, cbsa-crecust, #4952) |
| L6 | LE | LE date/time services: Lilian date / seconds semantics and the documented feedback codes; GMT is the pinned clock; the VSTRING output layout assumed; open conditions refused by name | MATCHED / ASSUMED / REFUSED | no (CBSA BANKDATA, the caller of CEEGMT and CEEDATM, has no equivalence case: its CUSTOMER-FILE and its Db2 estate are not a case yet) |
| A1 | assembler | CardDemo's COBDATFT, translated instruction for instruction; load-module-dependent paths refused | MATCHED / REFUSED | yes (CardDemo READACCT) |
| A2 | z/OS control blocks | a batch program's PSA -> TCB -> TIOT walk reads stand-in blocks built from the stated step; no step stated is refused | ASSUMED | yes (CardDemo CBSTM03A; det and oracle modelled, equivalence case pending) |
| Q1 | Db2 | Db2 for Linux runs the SQL, not Db2 for z/OS | ASSUMED | yes |
| Q2 | Db2 | EXEC SQL keeps RETURN-CODE | ASSUMED | yes |
| Q3 | Db2 | The unit of work: one per CICS task; one per batch step, ended by EXEC SQL COMMIT / ROLLBACK (cursors closed as Db2 for z/OS closes them), backed out by an abend, with SAVEPOINT / ROLLBACK TO SAVEPOINT / RELEASE SAVEPOINT run by Db2; a CICS program's ROLLBACK refused (-926) | MATCHED | CICS: yes (CBSA XFRFUN); batch: yes (synthetic UOWDEMO, `tests/equivalence/db2/uow`, #4269) |
| Q4 | Db2 | dynamic SQL beyond a literal INSERT (and its USING-bound markers), CONNECT, CALL, scroll FETCH, host-variable arrays; a savepoint statement in a CICS program | REFUSED | — |
| Q5 | Db2 | DSNTIAC / DSNTIAR message formatting | STAND-IN | no |
| Q6 | Db2 | Date and time text in ISO form; DDL adapted from z/OS jobs | ASSUMED | yes (CBSA, GenApp) |
| Q7 | Db2 | `CCSID EBCDIC` tables hold Unicode text: string order differs | DIFFERS | no |
| Q8 | Db2 | Positioned UPDATE / DELETE: the Java side by row id | MATCHED | yes (GenApp LGUPDB01) |
| Q9 | Db2 | More host variables than columns: SQLWARN3, the rest untouched | MATCHED (declared difference: SQLWARN3) | yes (GenApp LGUPDB01) |
| Q10 | Db2 | A statement the driver fails with no Db2 SQLCODE (a blank timestamp host variable) | REFUSED (the task; an enumerated fault task not judged) | yes (GenApp LGTESTP4: its add's enumerated fault task `add--sql-lgapdb01-316` (SELECT LASTCHANGED faulted), not run) |
| I1 | IMS | CBLTDLI GU GHU GN GHN GNP GHNP ISRT REPL DLET on a stated hierarchy (DBD / PSB sources, a seed), status codes from IBM's table, RETURN-CODE 0 after each call | ASSUMED | yes (CardDemo PAUDBUNL, carddemo-paudbunl, #4893) |
| I2 | IMS | twins and qualifications compare the field's stored bytes; a C / X key's order is the data page's (ASCII on both sides), not EBCDIC's; a P qualification only where packed and logical comparison agree | DIFFERS | no (CardDemo's keys are packed and binary bytes, the same in both pages) |
| I3 | IMS | position and parentage kept per PCB as IBM describes them; after a call whose position IBM leaves to IMS's search, the next call that needs it is refused | ASSUMED | yes (PAUDBUNL: GN after GNP's GE) |
| I4 | IMS | DBD name, level, status, PROCOPT, segment name, key feedback length, sensitive segments, key feedback as IBM lays them out; what IMS leaves there at entry and after GE / II assumed | ASSUMED | yes (PAUDBUNL tests PAUT-PCB-STATUS; its key feedback is only DISPLAYed on a path no scenario takes) |
| I5 | IMS | EXEC DLI beyond SCHD / TERM / GU / GN / GNP / ISRT / REPL / DLET and a BMP's CHKP ID, MPP programs, a GSAM PCB that reads, other calls (XRST, ROLB, CHKP with an option but ID, ...), command codes but F / L / P / C / D / N / Q / U / V / -, the # (independent AND) operator, AIBTDLI, CEETDLI in a BMP, HDAM order, secondary indexes, logical relationships, load mode beyond a lone L / LS PCB | REFUSED | — |
| I6 | IMS | an HD reorganization unload (DFSURGU0) read by the record layout observed in CardDemo's; the segment counts its trailer records must match what was read | ASSUMED | yes (carddemo-paudbunl: 22 roots, 202 children) |
| W1 | MQ | CMQV / CMQODV / CMQMDV / CMQGMOV / CMQPMOV / CMQTML: stand-ins from IBM's docs, version-1 layouts, only the constants the model gives meaning to | ASSUMED | yes (carddemo-codate01, #4892) |
| W2 | MQ | MQGMO_WAIT on an empty queue: 2033 at once (no concurrent producer); MQWI_UNLIMITED refused | ASSUMED | yes (carddemo-codate01, #4892) |
| W3 | MQ | the queue manager and its local queues are case facts; MSGDLVSQ(PRIORITY), DEFPRTY / DEFPSIST stated (default 0 / NO) | ASSUMED | yes (carddemo-codate01, #4892) |
| W4 | MQ | a generated MsgId is GGMQ + a 20-digit counter; a stated message's is GGMQSTATED + its number; handles 1, 2, 3 ... | ASSUMED | yes (carddemo-codate01, #4892) |
| W5 | MQ | gets / puts under syncpoint joined to the CICS UOW (z/OS default: in it); BackoutCount counted; MQCMIT / MQBACK / MQBEGIN refused | ASSUMED | yes (carddemo-codate01, #4892) |
| W6 | MQ | only MQOPEN / MQGET / MQPUT / MQPUT1 / MQCLOSE from a CICS program, Hconn MQHC_DEF_HCONN; every other MQI call refused by name | REFUSED | yes (carddemo-codate01, #4892) |
| W7 | MQ | CONVERT with the message's own CCSID and encoding (MQCCSI_Q_MGR: the queue manager's, stated, default 37) is a no-op; any conversion refused | REFUSED | yes (carddemo-codate01, #4892) |
| W8 | MQ | DEFAULT_CONTEXT: PutApplType MQAT_CICS, PutDate / PutTime the case clock as GMT, UserIdentifier / AccountingToken / PutApplName placeholders; NO_CONTEXT blank | ASSUMED | yes (carddemo-codate01, #4892) |
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
- **IBM's rule (quoted, #4702).** Enterprise COBOL for z/OS 6.4 Programming Guide, SC27-8714-03, Appendix A,
  "Fixed-point data and intermediate results" (p. 795), table "the precision theoretically possible": `+` or `-`
  integer places "(i1 or i2) + 1, whichever is greater", decimal places "d1 or d2, whichever is greater"; `*` i1 + i2
  and d1 + d2; `/` (op1 the divisor, op2 the dividend) integer places "i2 + d1", decimal places "(d2 - d1) or dmax,
  whichever is greater". dmax is the largest of the decimal places of the final result field(s), of any operand
  except divisors or exponents, and of any function's outer-dmax. In compatibility mode (`ARITH(COMPAT)`, the
  default) "a maximum of 30 digits is used for fixed-point intermediate results" (31 under `ARITH(EXTEND)`), and the
  next table fixes what is carried when i + d exceeds it: i + d over 30 and d at most dmax keeps d and gives `30-d`
  integer places; d over dmax keeps `30-i` decimal places (i + dmax at most 30) or `30-dmax` integer and dmax decimal
  places. "Truncated intermediate results" (p. 797): "Whenever the number of digits in an intermediate result
  exceeds 30 in compatibility mode or 31 in extended mode, the compiler truncates to 30 (compatibility mode) or 31
  (extended mode) digits and issues a warning. If truncation occurs at run time, a message is issued and the
  program continues running." Read from the manual's text (fetched 2026-10-17), not run on z/OS.
- **Options.** The rule depends on `ARITH` (the resolver's option, #4704): COMPAT 30, EXTEND 31. The det port reads it through the
  resolver, which defaults to COMPAT. TRUNC does not enter it (a statement's final store is C1 / C4).
- **The oracle.** `cobc -std=ibm` turns on GnuCOBOL's `arithmetic-osvs` (`ibm-strict.conf`), so cobc truncates
  intermediates (`cob_decimal_align`) with decimal places it works out at compile time from those rules. The
  reproducer of #4287 is IBM's own: `COMPUTE R = A / B * C` with A = 1, B = 3, C = 300 and R `PIC 999V99` gives
  099.00 (A / B kept to 2 places). The 30-digit truncation is the part of the rule the oracle does not apply: the translator replays cobc's places
  decision and `Cobol.align`, which has no 30-digit cap, and no cobc option, config key or wrapper of ours turns
  one on. **Measured 2026-10-18 (#4702)** on the pinned image (`gitgalaxy-gnucobol:3`, GnuCOBOL 3.1.2,
  `cobc -x -std=ibm`) with A and B `PIC 9(18)` both 999999999999999999, so A * B is 36 digits: `COMPUTE R = A * B / A`
  gives `R1=999999999999999999`; `COMPUTE S = A * B / (A * B) * 7` (S `PIC 9(2)`) gives `S1=07`;
  `A * B / A * T / T` (T = 10) gives `R2=999999999999999999`; `(A + B) * T / (T * 2)` gives `R3=999999999999999999`.
  Every result is the exact one, no cap and no warning. IBM under ARITH(COMPAT) truncates the 36-digit product to 30
  digits, so it would not give these. Pinned by `tests/cobol_mainframe/test_oracle_intermediate_cap.py`. So a result
  of 31 or more digits that IBM truncates to 30 (with a warning, the run continuing) the oracle keeps: a DECLARED
  oracle-vs-IBM difference (measured, not matched) the comparator expects, IBM's side quoted. No proven intermediate is known to be that long (ASSUMED; the det sweep's emitted truncations are
  the 2-place one under "Reached"), and a proof of a program that reached it would have to be recorded at the lower
  level. Under `ARITH(EXTEND)` (31 digits, C5) the det runtime enforces it instead: an add, subtract, multiply or
  divide that produces more than 30 digits stops by name (`RT-NUM-ARITH-EXTEND-STOP`, #4706).
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
- **Chosen behaviour.** MATCH THE ORACLE on places (the translator replays cobc's decision) and on the missing
  30-digit cap under COMPAT; STOP BY NAME past 30 digits under EXTEND (C5). Neither is IBM's quoted rule exactly, so
  both stay DIFFERS until a z/OS run (Part 2) measures a case.
- **To settle.** The oracle side of the 30-digit cap is measured (above); only the IBM side is open: a table of division, multiply-then-divide and binary-sum cases on z/OS against
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
  COBOL for z/OS 6.4 Language Reference, SC27-8713-03, MOVE statement, "Elementary moves", p. 404). The
  size-error rule for arithmetic statements reads: "If the ON SIZE ERROR phrase is not specified and a size
  error condition occurs, truncation rules apply and the value of the affected resultant identifier is computed"
  (same manual, "SIZE ERROR phrases", p. 297), and the largest value a binary result can hold is its PICTURE's
  "regardless of the TRUNC compiler option". Neither text says the sign is dropped for an unsigned arithmetic
  receiver, so that an arithmetic store follows MOVE's absolute-value rule is still inferred, not quoted (#4702;
  settled only by a z/OS run, Part 2). Under TRUNC(BIN), and for COMP-5 whatever TRUNC says, a binary receiver is "truncated only at halfword, fullword, or
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

### C5. Compiler options: NUMPROC MATCHED where IBM pins it (#4271); TRUNC(OPT) and ARITH(EXTEND) MODELLED (#4706); INTDATE(LILIAN) MODELLED in the det port, refused by the oracle
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
- **ARITH(EXTEND): MODELLED (#4706), as C2 describes.** EXTEND differs from COMPAT only for an intermediate result past
  30 digits (31 instead) and for float-mode precision (extended instead of long). The oracle compiles it as COMPAT
  (GnuCOBOL caps neither, C2); the det runtime computes COMPAT and stops by name (`Cobol.swapArithExtend(true)`,
  rule `RT-NUM-ARITH-EXTEND-STOP`: "ARITH(EXTEND): an intermediate result of N digits (past 30) is not modelled")
  wherever an add, subtract, multiply or divide would produce more than 30 digits, so a scenario either stays where
  COMPAT and EXTEND agree or is not judged. A floating-point expression under EXTEND is still refused at translation
  (`Untranslatable`). A port without the stop (model, generated) is proven as COMPAT, a declared difference in its
  evidence record (`option_differences`). Among the burned estates only DBB's EPSCSMRD carries `PROCESS ARITH(EXTEND)`.
- **INTDATE(LILIAN): MODELLED in the det port (#4706), REFUSED by the oracle.** IBM pins it (day 1 is 15 October 1582
  instead of 1 January 1601: the same date is 6653 higher). The translator reads the option through the one resolver
  (`program.intdate_lilian`: CBL / PROCESS cards over the compile step's PARM over the default, ANSI) and emits
  `Funcs.integerOfDateLilian` / `dateOfIntegerLilian` for INTEGER-OF-DATE / DATE-OF-INTEGER (rule
  `RT-FUNC-DATE-INTEGER`); it is fixed at translation, with no run-time switch. GnuCOBOL has no INTDATE, so
  `COBC_OPTIONS` still refuses it (`UnsupportedOption`): a LILIAN program is not compared with cobc, and the port is
  checked against IBM's documented day numbers (`test_intdate_lilian.py`), residual risk stated. Dates before day 1 of
  the count are not defined by IBM and are not judged. No burned estate's program carries `INTDATE(LILIAN)` (#4271
  status check, re-confirmed by #4706's slice 2), so no estate port changed.

### Compile options: the table (#4706)
One row per option that can change a result: (1) does it change results; (2) can cobc honour it; (3) what the det
port does; (4) otherwise refused by name or a declared difference (#4702: IBM is the reference, GnuCOBOL the
instrument). The rows below are rendered by one table in code (`compiler_options.OPTION_TABLE`; `estate_options.EffectiveOptions.unhonoured`): the estate's PARM, installation defaults and CBL cards are resolved against it, so an option the harness cannot honour is no longer merely recorded. Citations: Enterprise COBOL for z/OS 6.x Programming Guide, "Compiler options", the option's own section; the defaults are those the 6.4 page lists (FLOAT's default is not on it: HEX is what register C6 models).

| option | (1) changes results? | (2) cobc | (3) det port | (4) otherwise | register |
|---|---|---|---|---|---|
| `TRUNC(STD)` (IBM default) | yes: a binary receiver keeps its PICTURE's digits | `-fbinary-truncate` | `Cobol.swapTruncBinary(true)` | -- | C1 |
| `TRUNC(BIN)` | yes: a binary receiver keeps its bytes | `-fnotrunc` | `Cobol.swapTruncBinary(false)` | -- | C1 |
| `TRUNC(OPT)` | only for a binary value past its PICTURE, where IBM's result is unpredictable; conforming values compute as STD | `-fbinary-truncate` (STD: equal for conforming values) | STD, plus `Cobol.swapTruncOpt(true)`: a value past a COMP / COMP-4 / BINARY receiver's PICTURE stops by name ("TRUNC(OPT): value exceeds PICTURE; IBM result unpredictable") | a port without the stop (model, generated) is proven as STD: a declared difference (`option_differences`) | C1, C5 |
| `ARITH(COMPAT)` / `ARITH(EXTEND)` | yes: EXTEND widens intermediates to 31 digits and floats to extended precision | COMPAT flags (no cap on either side, C2) | COMPAT, plus `Cobol.swapArithExtend(true)`: an intermediate past 30 digits stops by name ("ARITH(EXTEND): an intermediate result of N digits"); a float is refused | a port without the stop is proven as COMPAT: a declared difference (`option_differences`) | C2, C5 |
| `INTDATE(ANSI)` / `INTDATE(LILIAN)` | yes: day 1 of INTEGER-OF-DATE moves from 1601-01-01 to 1582-10-15 | none for LILIAN | `Funcs.integerOfDateLilian` / `dateOfIntegerLilian`, picked at translation | the oracle refuses `INTDATE(LILIAN)` by name (`COBC_OPTIONS`); the port is checked against IBM's day numbers, not cobc | C5 |
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
| `ZWB` (IBM default) / `NOZWB` | yes: whether a signed zoned operand of a numeric-vs-nonnumeric comparison is compared with or without its sign (C13) | none | none (compares unsigned) | `NOZWB` refused by name; no burned estate names either option (2026-10-20) | C13 |
| `NOINITCHECK` (IBM default) / `INITCHECK` | no: compile-time warnings for uninitialised items | none needed | -- | recorded only | C5 |
| `OPTIMIZE(0\|1\|2\|STD\|FULL)` | no for defined behaviour: run time and storage | none needed | -- | recorded only (CBSA's `OPT` = `OPTIMIZE(1)`); a zero divisor without ON SIZE ERROR is undefined on IBM at every level, so the det port follows cobc whatever the level; no proven scenario divides by zero | C5, C14 |

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
  - **Three more oracle differences, decided for IBM (#4688, seen by the #4675 fuzz; GnuCOBOL 3.1.2).** The port keeps
    its answer in each; the vectors are in `test_det_hfp.py`. (1) `MOVE G TO E`, G COMP-1 = 1.875, E `-(5)9.99`: the
    port gives 1.88 (IBM rounds a float moved to a fixed-point or edited item in the low-order position, "Conversions
    and precision"), cobc 1.87. (2) `COMPUTE R1 = ((FA / 2) * (0.5 + F4))`, FA COMP-1 5, F4 COMP-2 4, R1 `S9(7)V99`: the
    port gives 11.25 (long HFP, 2.5 * 4.5, exact), cobc 0.00 (the decimal evaluation above). (3) `ADD FZ2 TO R4`, R4
    `S9(7)V99 COMP-3` = 0.68, FZ2 a COMP-2 zero: the port gives 0.67. IBM runs any statement with a floating-point
    operand in floating point (even a zero one), 0.68 is 0.67AE147AE147AE x 16**0 in long HFP (just below 0.68), and
    the store truncates (ASSUMED, below; pending z/OS calibration, #4702 part 2); cobc keeps 0.68. None of the three
    shapes is in a burned estate's program (EPSMPMT's float use is the `**` below). Each is a z/OS-runnable probe in `zos_probes.json` (`c6-float-move-to-edited`,
    `c6-compound-float-compute`, `c6-float-zero-add-to-packed`) with the oracle's answer recorded; no z/OS result yet.
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
  modification, STRING, a CALL argument, a record read or written -- a file or sort record named by its FD through
  `Gen.check_record_bytes`, #4271 -- a COMMAREA); a float MOVEd to or from a nonnumeric item;
  a comparison with a nonnumeric operand; an intrinsic function in one but NUMVAL / NUMVAL-C (IBM's floating-point functions);
  any floating-point expression under ARITH(EXTEND); ON SIZE ERROR and ROUNDED into a float, DIVIDE ... REMAINDER
  in floating point. In the runtime: an HFP exponent overflow or underflow (a `**` result included), `0 ** 0` and 0 to a negative power, a negative base with a fractional exponent, an integer exponent past +-1000 (base other than 1 or -1) (what z/OS does depends on the program
  mask and Language Environment), a NUMVAL argument past 18 digits or 15 significant ones. `ggdisplay.c` still
  refuses the DISPLAY of a float on the COBOL side (C8), so no proof compares one.
- **Waiting on it.**
  - `mortgage-mpmt` (EPSMPMT): its interest rate is now computed in long HFP, but the payment's `(1 + C) ** N`, N
    with decimal places, is a floating-point exponentiation: since the `**` slice below it translates (ASSUMED
    `Hfp.power`), but no z/OS capture agrees with the assumption, so the case stays unproven. Its det port is in the
    det sweep's baseline (KNOWN_UNPROVEN) for the one hole left, the dead-code `FUNCTION ANNUITY` (#5867). Its
    callers `mortgage-csmrt` and `mortgage-cmort` are listed only through the called-hole rule. It would also round
    where GnuCOBOL truncates.
  - **A non-exact COMP-2 amount into a 2-decimal field (#5703 evidence, BNK1TFN line 494).** 12.34, 9999999999.99 and 0.01
    moved to `S9(10)V99` differ between GnuCOBOL and the port where the double is below the decimal (12.34 -> cobc 12.33,
    9999999999.99 -> cobc 9999999999.98, port 12.34 / 9999999999.99). IBM's MOVE rounding is documented ("Conversions and
    precision"), so this is a DECLARED difference, not an open question: the port follows IBM, the case draws only values
    exact in both formats (100.50, 12.75), and the vectors are pinned by `test_det_hfp.py`
    `test_a_cbsa_comp2_amount_moved_to_a_two_decimal_field_rounds_where_the_oracle_truncates` (COMP-1: nine significant
    digits, `test_a_comp1_amount_moved_to_a_two_decimal_field_keeps_nine_significant_digits`). Still pending z/OS capture (#4050).
  - **LE seconds as a COMP-2 moved to a `9(14)` field (BANKDATA `TIMESTAMP`: CEEGMT `gmt-seconds`; CRECUST: CEELOCT
    `WS-TODAY-SECONDS`).** The source comment moves the float to an integer "so that we don't round up"; the model
    rounds a float MOVEd to fixed point ("Conversions and precision"), GnuCOBOL truncates, so 13987654321.6 seconds
    gives 13987654322 in the port. A whole second is exact in long HFP. A DECLARED difference, asked by four
    `model-assumption` records (`asm-enc-13987654321*-long`, `asm-fixed-13987654321*-long-0`), pinned by
    `test_the_bankdata_le_seconds_shape_is_asked`. Still pending z/OS capture (#4050).
  - **A rate NUMVALed into a COMP-1 (BNK1UAC / BNK1CAC `INTRTI-COMP-1`) and a 14-digit integer into a COMP-2 (BANKDATA
    `COMPUTE period-next = period-next-f`).** `IF INTRTI-COMP-1 > 9999.99` compares the short item widened to long
    with the long literal: short 9999.99 (`44270FFD`) is below long 9999.99 (`44270FFD70A3D70A`), so exactly 9999.99
    passes the check; `MOVE INTRTI-COMP-1 TO INT-RT-9` (`9(4)V99`) gives 0.70 for 0.7 (GnuCOBOL: 0.69). A 14-digit
    integer is exact in long HFP. Asked by eight `model-assumption` records (`asm-enc-0.7-short`, `asm-*-9999.99-*`,
    `asm-cmp-9999.99-short-long`, `asm-*-99999999999999-long*`), pinned by
    `test_the_bnk1uac_rate_and_bankdata_period_shapes_are_asked`. Still pending z/OS capture (#4050).
  - **A COMP-2 amount negated, compared with ZERO and MOVEd on (BNK1CRA `WS-AMOUNT-AS-FLOAT`, lines 495-498, 1133).**
    `COMPUTE X = X * -1` is an exact long multiply by -1 (`mul-long-12.34-neg1`), `IF X = ZERO` compares both signs
    (`cmp-long-12.34-zero`, `cmp-long-neg-12.34-zero`) and the MOVE to the 2-decimal amount rounds a negative value
    (`asm-fixed-neg-12.34-long-2`, model-assumption). Asked as 4 records (85 asked then), pinned by
    `test_the_bnk1cra_amount_shapes_are_asked`. Still pending z/OS capture (#4050).
  - **A monthly interest rate stored in a COMP-1 and added to 1 (DBB EPSMPMT `WS-CALC-INTEREST`, lines 120-130).** The
    quotient `(rate / 100) / 12` is not exact (5% is 0.0041666...), stored as short HFP (`3F111111`), read back at 8
    places (0.00416667), and `1 + rate` is a long add (`4110111111000000`); the `**` after it is the ASSUMED routine below. Asked
    as 5 `model-assumption` records (90 asked in all; `asm-*-eps-*`), pinned by `test_the_epsmpmt_interest_shapes_are_asked`.
    Still pending z/OS capture (#4050).
  - **The exponentiation after it (DBB EPSMPMT lines 125-130, `(1 + WS-CALC-INTEREST) ** WS-NUMBER-OF-MONTHS`).** The kit has
    a `pow` op (`COMPUTE LR = LA ** LB`, long only: a short `**` is skipped like a short multiply). IBM documents no result,
    so the 5 `asm-pow-eps-*` records (95 asked in all) are `model-assumption` records whose `want` is the kit's own reference
    (`hfp_capture_kit.power`: the exact power for an integer exponent, `exp(b ln a)` at 60 digits for a fractional one,
    truncated to long): 5% over 360 months, 12, 2.5 and -12, and 6.5% over 360. The base is the `1 + rate` long add above,
    the exponent the month count (`9(9)V99 COMP`) converted to long. They are evidence of nothing until z/OS agrees; the
    det runtime now uses the same routine (`**` below) and `mortgage-mpmt` stays in KNOWN_UNPROVEN. Pinned by
    `test_the_epsmpmt_exponentiation_is_asked`.
  - CBSA's CRECUST, BANKDATA, BNK1CAC, BNK1CRA, BNK1TFN and BNK1UAC are not cases. Since #4270's NUMVAL slice
    BNK1CAC, BNK1TFN and BNK1UAC translate whole (BNK1CRA still has EXEC CICS INQUIRE).
- **Exponentiation in a floating-point expression is an ASSUMED routine (#4271).** IBM documents no result for `**`.
  The det translator emits `Hfp.power(base, exponent)` in every shape (a COMP-1 or COMP-2 base, a fixed-point base with
  a float exponent, a parenthesised base, an exponent that is a literal, an item, negative, with decimal places or a
  float, COMPUTE or IF, nested, any receiver). A `**` makes the statement LONG, so the routine is long HFP: the exact
  power for an integer exponent, `exp(b ln a)` at 60 digits for a fractional one, truncated to long. It is the capture
  kit's reference (`hfp_capture_kit.power`, the `want` of the 5 `asm-pow-eps-*` records) and the Java runtime is held
  to the translator's model `det/hfp.py power` bit for bit; pinned by `test_det_hfp.py`
  `test_a_floating_point_exponentiation_translates_through_hfp_power_in_every_shape`,
  `test_the_power_routine_is_the_model_bit_for_bit` and `test_the_model_power_is_the_capture_kits_reference`. It is
  evidence of nothing until a z/OS run agrees (#4050): a disagreeing capture is a finding against this routine, and
  `mortgage-mpmt` stays in KNOWN_UNPROVEN (the oracle cannot run HFP). Refused by name: a range overflow or underflow,
  `0 ** 0`, 0 to a negative power, a negative base with a fractional exponent, an integer exponent past +-1000. A
  fixed-point `**` is not affected (the oracle's decimal rule, C2; `test_a_fixed_point_exponentiation_is_not_refused`).
  `FUNCTION ANNUITY` (the same power plus an undocumented float result) stays a Hole. Among the burned estates only
  EPSMPMT (line 125) reaches it.
- **What would settle it.** A z/OS run of EPSMPMT's scenarios (#4050): the exponentiation, and the ASSUMED
  conversions above, checked where the oracle cannot.
  - **Where a capture lands (#4271, #4050).** `tests/cobol_mainframe/zos_captures/hfp.json` is a table of expected HFP
    results (encode, add / sub / mul / div, display, float to fixed, `from_ieee` / `to_ieee`, `round_short`, `compare`), checked against `det/hfp.py` by
    `test_hfp_zos_captures.py` (the Java runtime is held to that model bit for bit by `test_det_hfp.py`). It holds
    75 `ibm-publication` records covering every operation in both sizes (`round_short`, a long item MOVEd to a COMP-1, is short only: LOAD ROUNDED half away from zero, the carry into the exponent, a negative and a zero; `compare` is algebraic: an unnormalized image equals its normalized one, -0 equals +0, one last-digit step orders) (the IEEE conversions: 1, -118.625, 1.5, 100.5, 0, and 0.1 in binary64, whose image differs from IBM's truncated 0.1) (long sub / mul / div / display / fixed, the
    guard digit kept and lost, truncation, the range ends, a float-to-fixed 9-digit clamp); `test_the_table_covers_every_op_in_both_sizes`
    keeps that matrix whole (`SIZES` names the one op that is short only). It holds only `ibm-publication` records today; NO `zos-run` record exists. A `zos-run` record needs `evidence` (job, step,
    output hash, never the data) and `calibrated_under` (`runtime_options.calibration_problems`, #4702). A model that
    disagrees with a captured record is a finding against the model: fix the model, never the record.
  - **The burned-float census (#4271).** `test_hfp_burned_float_census.py` reads the burned estates' sources and requires
    every COMP-1 / COMP-2 item (8 items in 7 programs: BANKDATA, CRECUST, BNK1CAC, BNK1UAC, BNK1CRA, BNK1TFN, EPSMPMT) to
    be claimed with the lines that name it and with records that exist in `hfp.json`; a new float item, or a statement
    that moves or is added, fails until a record asks the shape. What is still missing for the checklist item is a
    `zos-run` record (none exists), not a shape.
  - **The capture kit (#4271, #4050).** `tests/tools/hfp_capture_kit.py emit OUTDIR` writes `HFPCAP.cbl` / `HFPCAP.jcl` from
    the table's `ibm-publication` records: a program (Enterprise COBOL 6.3 or later, `FUNCTION HEX-OF`) that runs each
    operation on z/OS and DISPLAYs `id|result`; `ingest SYSOUT --job J --step S --calibrated-under OPTIONS.json` appends
    one `zos-run` record per captured line (evidence: job, step, the output's sha256; the options through
    `calibration_problems`), never rewrites an existing record, and reports a model that disagrees as a finding (the
    record stays, the model is fixed). 50 `ibm-publication` records are asked of the COBOL program; the 28 it cannot ask are asked by **HFPCAPA**, a High Level
    Assembler program `emit` writes beside it (`HFPCAPA.asm` / `HFPCAPA.jcl`, `ASMACLG`, `OPTABLE(UNI)`): the 22 IEEE conversions
    (COBOL has no IEEE converter) through the CONVERT HFP/BFP instructions (`THDER` / `THDR`, `TBEDR` / `TBDR` with M3=4, round to
    nearest even) and the 6 short multiply / divide rows (IBM evaluates a COMP-1 multiply or divide in long floating point in COBOL)
    through `MEER` / `DER`, the short arithmetic itself. Same `id|HEX` lines; `verify` / `ingest` take `--kit asm` for its SYSOUT
    (the G step's SYSPRINT). Only a short `**` stays unasked. The assembler text is not assembled by any test (no HLASM here):
    `test_hfp_capture_kit.py` holds its instruction choice, column limit and the ingest of model-computed output, so the first
    z/OS assembly may need a syntax fix, which changes no record.
    **Model-assumption probes (#4271).** 22 `model-assumption` records (`asm-*`) ask the ASSUMED rules above too, so
    the first z/OS run settles them: a fixed-point value converted to long (0.3, 123.45, -0.3; to short, 0.3), a float's
    DISPLAY mantissa (long and short images of 0.1, short 0.7), and the new `store` op, a COMPUTE of a fixed-point
    receiver from two long operands, truncated and `ROUNDED` (0.1 + 0.2 to 2 places: 0.29 / 0.30; 2 / 3: 0.66 / 0.67;
    0.7 * 3). Their `want` is the model's own answer and the source never counts as IBM's word; a z/OS result that
    differs is a finding against the model like any other. Asked: 81 records.
    **The BNK1TFN shape (#4271, PR #5703's evidence).** A non-exact COMP-2 (12.34, 0.01, 9999999999.99; the first two
    also as COMP-1) MOVEd to a 2-decimal field gives a different answer on GnuCOBOL (truncates the float) and on the
    det port (rounds in the receiver's low-order position, "Conversions and precision"); IBM is not settled by a run.
    10 more `asm-enc-*` / `asm-fixed-*` records ask the image and the digits, so the first z/OS run settles it; until
    then the BNK1TFN case draws only exactly-representable amounts.
    **Runbook (the checklist's remaining steps).** (1) `emit OUTDIR`, compile with Enterprise COBOL 6.3 or later and run
    `HFPCAP.jcl` on z/OS, keeping the job's SYSOUT, and assemble and run `HFPCAPA.jcl` too (its `--kit asm` output); (2) `verify SYSOUT` is a dry run (no job, step or options needed, nothing
    written, exit 1 on a finding): read its `findings` (the model disagrees with z/OS), `missing` and `skipped`; (3) fix any
    finding in `det/hfp.py` and `Hfp.java`, never a record; (4) `ingest SYSOUT --job J --step S --calibrated-under
    OPTIONS.json` appends the `zos-run` records; (5) re-check EPSMPMT's float `**` and the `reached:` line above.
    Proven by `test_hfp_capture_kit.py` with model-computed output (never written to the table). **The kits are not a
    capture: no `zos-run` record exists, and the checklist's proof against captured outputs still waits on #4050.**
  - **Remaining lines of the hex-float checklist item (#4271, split after nine partial slices).** The model, the Java
    runtime, the power routine, the `ANNUITY` refusal, the capture table, the burned-float census and the HFPCAPA lint are
    merged; what is left is one external step and three PRs behind it, in this order:
    (1) a z/OS run of HFPCAP and HFPCAPA, SYSOUT kept (owner action, #4050; not agent work);
    (2) PR: `ingest` the HFPCAP SYSOUT as `zos-run` records, and settle any ASSUMED rule the run disagrees with (power,
    store, DISPLAY, float-to-fixed) in `det/hfp.py`, `Hfp.java` and `cobolrt_rules.json`, never in a record;
    (3) PR: `ingest --kit asm` the HFPCAPA SYSOUT, and re-check EPSMPMT's float `**` against it;
    (4) PR: if the `**` agrees and `FUNCTION ANNUITY` is closed (#5867), move `mortgage-mpmt`, `mortgage-csmrt` and
    `mortgage-cmort` out of `KNOWN_UNPROVEN` and `det_sweep_baseline.json`, update this register and the ground-truth ledger.
    Burned programs gated: EPSMPMT (lines 2-4). Unsettled siblings: `FUNCTION ANNUITY` stays a Hole (EPSMPMT only); a
    non-exact COMP-2 MOVEd into a 2-decimal field differs between GnuCOBOL and the det port (BNK1TFN, line 494), IBM
    behaviour unsettled, so the CBSA case draws only exactly-representable amounts.
- **IEEE <-> HFP conversion model (#4271).** `det/hfp.py` `ieee_value`, `from_ieee`, `to_ieee`, `exact_in_both`, proven by
  `test_hfp_ieee.py`: a binary64 fits long HFP exactly (53 bits in 56) and converts back to the same pattern; a short
  HFP inside binary32's normal range (about 1.2e-38 to 3.4e38) is exact in binary32; a long HFP rounds to binary64 half
  to even; a binary32 takes the fixed-point-to-float rule (truncated to long, rounded to short: ASSUMED, IBM documents no
  IEEE converter). NaN, infinity, subnormals and values outside either range are refused by name (`HfpRange`).
  `exact_in_both` is the register's "agrees with the oracle only for values exact in both formats" condition (1.5,
  2.25, 100.50, 12.75 yes; 0.1, 0.7, 12.34 no). The runtime mirrors the conversions (`cobolrt/Hfp.java` `ieeeValue`, `fromIeee`,
  `toIeee`, rule `RT-HFP-IEEE-CONVERSION`, ASSUMED), held to the model bit for bit by `test_det_hfp.py` over IBM's examples, the
  range edges, the refusals and random patterns in both sizes; no COBOL statement reaches them yet. **No `zos-run` capture exists, so
  the checklist's proof against captured z/OS outputs still waits on #4050.**
- **Later slices of #4271** (left as they are): `NUMPROC(PFD)` with non-preferred signs (refused by name, C5),
  `INTDATE(LILIAN)` (detected from CBL / PROCESS cards and refused, C5); ARITH(EXTEND)'s extended-precision floats (refused; its 30-digit intermediates stop by name, C5), COMP-5's
  z/OS byte order where bytes are observable (C7).

### C7. COMP-5 byte order — DIFFERS; byte uses refused by name
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
- **Refused by name (#4271).** The det translator no longer proves a program on the oracle's byte order: a COMP-5 item
  of 2 or more bytes whose bytes are observed -- a group holding it used as a whole (MOVE, compare, 88), a REDEFINES
  over it by a non-COMP-5 item, a reference modification of it -- is a Hole ("COMP-5 is little-endian on the oracle,
  big-endian on z/OS: oracle_assumptions.md C7"), through the guard COMP-1 / COMP-2 use (`Gen.overlaps_float`,
  `comp5_extents`). Read as a number it is translated as before. Pinned by `test_det_programs.py`
  `test_comp5_bytes_are_refused_by_name_where_the_oracle_and_zos_differ`. `det_port.py check`: no committed port moved
  (119 of 119 unchanged), so no burned program observes COMP-5 bytes.
  - **File and sort records (#4271).** A record is named by its FD, so READ, WRITE, REWRITE, SORT USING / GIVING and
    RETURN reached its bytes without `field_expr`'s guard. `Gen.check_record_bytes` now refuses a record holding a
    COMP-5 item of 2 or more bytes (and, for C6, a COMP-1 / COMP-2 item) by name; pinned by `test_det_programs.py`
    `test_record_io_*`.
  - **Not covered (sibling gaps):** the SQLCA record (the SQL lane hands the whole group to the runtime, which sets
    its COMP-5 fields as numbers; a program that MOVEs the SQLCA as bytes is not refused); an elementary COMP-5 item
    passed BY REFERENCE to a CALLed program or in a COMMAREA (the callee reads the oracle's order); INITIALIZE and
    group VALUE images, which write numbers. Burned estates reading COMP-5 as numbers only: CardDemo
    `IMSFUNCS.cpy`, cics-async `SEQPNT` / `ASYNCPNT`, DBB `EPSCSMRD`.
- **Its size** for 1 or 2 digits differs too: C16.

### C8. DISPLAY text — MATCHED
- **What.** GnuCOBOL writes a signed zoned item as `012-` and a binary item as `-00007`. IBM writes their external
  decimal form with the sign overpunched (`01K`, `000P`). `ggdisplay.c` (LD_PRELOAD) rewrites each such operand as
  IBM does.
- **Refused.** An operand outside the model (floating point, more than 32 operands) writes `GGDISPLAY-NOT-MODELLED`,
  and that run's SYSOUT is not compared.
- **IBM.** Enterprise COBOL for z/OS 6.4 Programming Guide (SC27-8714-03), "Sign representation of zoned and
  packed-decimal data", and Language Reference (SC27-8713-03), "DISPLAY statement": DISPLAY writes a numeric item in its
  external form, so a signed zoned (external decimal) item carries its sign in the zone of its last digit (`{` / `A`-`I`
  positive, `}` / `J`-`R` negative in the displayed character set) and has no separate `-`. The overpunched text is
  IBM's, and `ggdisplay.c` produces it; GnuCOBOL's `012-` / `-00007` is the oracle's form, which the wrapper
  rewrites (the declared difference, closed by the rewrite).
- **Not quoted.** The exact text IBM writes for a signed COMP or COMP-3 item under DISPLAY (converted to external
  decimal first) is ASSUMED to follow the same overpunch rule; no z/OS run measures it (#4702 Part 2).

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
- **IBM's options for this data (quoted, #4702).** Enterprise COBOL for z/OS 6.4 Programming Guide, SC27-8714-03,
  "ZONEDATA" (p. 428): the option "tells the compiler whether the data in USAGE DISPLAY and PACKED-DECIMAL data items
  is valid, and if not, what the behavior of the compiler should be"; default `ZONEDATA(PFD)`: "the compiler assumes
  that all data in USAGE DISPLAY and PACKED-DECIMAL data items is valid". `ZONEDATA(MIG)` makes comparisons ignore
  the zone bits and avoids optimizations that would differ from COBOL 4 on invalid digits, sign codes or zone bits;
  `ZONEDATA(NOPFD)` behaves as COBOL 4 did under `NUMPROC(NOPFD | PFD)`. The manual notes ZONEDATA "is deprecated
  but is tolerated" and "replaced by the INVDATA option" (PFD = NOINVDATA, NOPFD = INVDATA(NOFORCENUMCMP,CLEANSIGN),
  MIG = INVDATA(FORCENUMCMP,CLEANSIGN)). Under the default no result is defined for a non-digit, so every shape
  below is either the oracle's rule (DIFFERS, the IBM side undefined) or refused by name; none is MATCHED except the
  same-shape MOVE (APAR PH21007, below). The options resolver honours only `ZONEDATA(PFD)` and refuses NOPFD / MIG and
  INVDATA (`gitgalaxy/core/compiler_options.py`), and `-std=ibm` gives one behaviour per shape (the table), which is why the proofs keep non-digit inputs out of the cases or say "cobc's bytes, not
  z/OS's". Chosen behaviour per shape: see each bullet; a z/OS run (Part 2) is the only way to turn DIFFERS into
  MATCHED or a measured difference.
- **Now.** Those inputs are not in the case, so the three COMEN01C survivors in the port's own digit test stay case
  gaps. A z/OS run (#4050, Part 2 of #4702) settles which side is right.
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
- **A non-digit in a POINTER / TALLYING item (#4692) -- REFUSED by name.** The same read-before-store as the receiver of
  ADD: `INSPECT ... TALLYING ctr` and `UNSTRING ... TALLYING IN ctr` add to the counter's current value, and
  `STRING ... WITH POINTER p` / `UNSTRING ... WITH POINTER p` read where to start. A zoned item holding a non-digit
  there (a counter cleared by `MOVE SPACES`) is refused at run time (`Cobol.counterNum`: "a STRING / UNSTRING pointer
  or tallying counter that is a zoned item holding a non-digit is not modelled"), on IBM's ground above (no result
  documented); a digit-only one counts as ever. Tested over the five receiver shapes x INSPECT ALL / CHARACTERS,
  UNSTRING TALLYING / POINTER, STRING POINTER, and the digit-only start of each (`test_det_nondigit_zoned.py`). A plain
  item (no REDEFINES) cleared to spaces and then ADDed to is refused too (the lifted-item path goes through the same
  `receiverNum`). `PERFORM VARYING` variables and `SET ... UP / DOWN BY` targets go through `receiverNum` too (#5404). ADD /
  SUBTRACT CORRESPONDING is not translated (a hole), so no dirty member reaches a read. ON SIZE ERROR, ROUNDED and
  several-receiver forms are refused alike (`test_det_nondigit_zoned.py`).
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
    item -- REFUSED (translation hole).** "Valid and invalid elementary moves" (Table 47, SC27-8713-03 pp. 404-405), row "Numeric noninteger
    sending item", columns alphabetic / alphanumeric / alphanumeric-edited: NO. cobc warns ("MOVE of non-integer to
    alphanumeric") and moves. A right-P item (`99PP`, `S99PP`) is an integer: the MOVE is valid and "any digit positions
    described with picture symbol P in the sending item are considered to have the value zero. Each P is counted in
    the size of the sending item" (MOVE, usage note 1), which is what the port and cobc do (`1200  ` for `12`). A
    non-digit in its digit positions is C11's undefined data, copied as for an unscaled item (the IBM rule for the
    digits is quoted from MOVE usage note 1, p. 404, and matches; IBM defines nothing for the non-digit, so that part
    is the oracle's bytes, DIFFERS-class like the rest of C11).
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
    Table 47 marks it invalid, and the translator refuses every national item (PIC N / G, USAGE NATIONAL / DISPLAY-1,
    an N / G / U literal) before generation (#4462, #4664), so no sender shape, noninteger or not, reaches a national
    receiver. Tested over `9V99`, `S9V99`, `VPP99`, `SVPP99`, `99PP`, `9(3)` x six national declarations
    (`test_det_nondigit_zoned.py`).
  - **UNSTRING -- REFUSED (translation hole), two different grounds (`Gen.unstring_operands`).** Quoted from the 6.4
    Language Reference (SC27-8713-03, UNSTRING, pp. 465-466; #4702):
    - "identifier-1 must reference a data item of category alphabetic, alphanumeric, alphanumeric-edited, DBCS,
      national, national-edited, or UTF-8"; identifier-2 and -3 (`DELIMITED BY`) the same list; identifier-5
      (`DELIMITER IN`) "alphabetic, alphanumeric, DBCS, national, or UTF-8". Numeric is in none of them, so a numeric
      sending, `DELIMITED BY` or `DELIMITER IN` item is a compile error on z/OS (IBM's rule, not the port's choice; the
      port refuses it by name, `UNSTRING sending item ...`). GnuCOBOL moves the stored bytes.
    - "identifier-4 must reference a data item of category alphabetic, alphanumeric, numeric, DBCS, national, or UTF-8.
      If the referenced data item is of category numeric, its picture character-string must not contain the picture
      symbol P, and its usage must be DISPLAY or NATIONAL": a numeric `INTO` item with a P is a compile error
      (refused as IBM does); a numeric DISPLAY `INTO` item without a P is valid, decimal places included.
    - "identifier-6 must be an integer data item defined without the symbol P" (`COUNT IN`); identifier-7
      (`POINTER`) and identifier-8 (`TALLYING IN`) the same: a non-integer or P item is a compile error (refused as
      IBM does).
    - Moves: "The rules for moving are the same as those for a MOVE statement for an elementary sending item of the
      category of identifier-1, with the appropriate identifier-4 as the receiving item" (p. 466), so an alphanumeric
      piece moved into a numeric item goes "as if the sending item were described as an unsigned integer" (MOVE, p.
      404). With no `DELIMITED BY`, the examined size of a numeric receiver is "the number of character positions in
      the integer portion of the current receiving field" (Table 54, p. 470), one less for SIGN IS SEPARATE.
    The one choice that is the port's own, not IBM's (REFUSED, a translation hole, nothing ASSUMED about z/OS): a
    decimal (no P) numeric `INTO` item. IBM defines it (the table above, the integer portion), GnuCOBOL moves its
    bytes, and the port does not translate either; an integer numeric `INTO` item and a reference-modified operand
    (alphanumeric) are translated as before. Not yet checked against the IBM text, listed as a gap: a numeric-edited
    UNSTRING sending item (the list above omits numeric-edited too).
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
- **Libraries that share the generator (#5561).** The Berkeley DB under GnuCOBOL's indexed files (`libdb-5.3.so`)
  and the Db2 client call `srand` (a time- or pid-derived seed, at file open) and `rand` in the same process, which
  cut the program's sequence: BANKDATA's customers differed on every oracle run. `tests/equivalence/faults/ggdisplay.c`
  (preloaded in every oracle run) answers `rand` / `srand` calls made from a `libdb*` library from a private
  generator and passes every other caller to libc, so the program's sequence is the one the port reproduces. z/OS
  shares no generator between VSAM, Db2 and the program; the isolation models that.
- **Known differences, unreached.** The oracle can return exactly 0 or 1 (`rand()` of 0 or `RAND_MAX`, about once in
  2^31 draws), IBM never does; the port follows the oracle. A LINKed program is a new run unit on z/OS (its own
  sequence from seed zero) but shares the task's process state in the oracle; the port gives each program its own
  sequence, so a task whose caller and LINK target both draw unseeded numbers would differ. A CALLed program shares
  its caller's run unit on z/OS; the port keeps the CALLed program's own sequence. No translated program reaches
  these: each one's first reference is seeded.
- **Reached.** `cbsa-bankdata` (L2, det sweep: 3 runs, 24/24 paragraphs, 17/48 branches) draws every customer and
  account field from seed 7's sequence and compares them (VSAM, ACCOUNT, CONTROL). No proof yet for LGICVS01. Pinned against
  GnuCOBOL by `tests/cobol_mainframe/test_det_programs.py` (`RANDOM`: an unseeded first reference, seeds 0,
  42, 1,234,567 and 2,147,483,647, CRDTAGY's and LGICVS01's COMPUTEs) and against glibc's own numbers by
  `test_det_funcs.py`.
- **To settle.** Only a z/OS run can give IBM's numbers; even then they would be data for a declared difference, not
  a model, since the generator is unpublished.

### C13. A numeric operand compared with a nonnumeric one — MATCHED where IBM and the oracle agree, REFUSED where they do not (#4665)
- **IBM** (Enterprise COBOL for z/OS 6.4 Language Reference, SC27-8713-03, "General relation conditions", the
  comparison-by-operand-class table and "Alphanumeric comparisons", p. 276; re-read 2026-10-17, #4702): the
  comparisons defined include "Two operands where one is a numeric integer and the other is class alphanumeric or
  national". The table gives "Alph (Int)" for a numeric literal or a zoned decimal item against an alphanumeric
  character item (alphanumeric, alphanumeric-edited, numeric-edited with usage DISPLAY) and no entry for a native
  numeric item (packed, binary, floating point) there, so IBM rejects those. "A zoned decimal integer operand is
  treated as though it were moved to a temporary elementary data item of category alphanumeric with a length the same
  as the total number of digits in the number, according to the rules of the MOVE statement. When the ZWB compiler
  option is in effect, the unsigned value of the integer operand is moved to the temporary data item. When the NOZWB
  compiler option is specified, the signed value is moved." The comparison is then character by character, the
  shorter operand extended on the right with spaces. ZWB is the default (6.4 Programming Guide, SC27-8714-03,
  "ZWB", pp. 430-431): it removes the sign of a signed zoned DISPLAY field before the comparison, P-scaled items
  always lose it, and NOZWB exists for testing numeric fields for SPACES. The entry is no longer ASSUMED; what is
  still unmeasured on z/OS is below.
- **Compile options.** The det port and the oracle compare the unsigned value, which is ZWB, IBM's default. `NOZWB`
  (PARM, installation default or a CBL / PROCESS card) is refused by name (`compiler_options.OPTION_TABLE`, C5), since
  a signed zoned item compared with its sign would be proven against the wrong rule. An explicit `ZWB` is honoured and
  cancels an earlier `NOZWB`. No burned estate names either option (a whole-word, case-insensitive search of the six burned estates -- CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication, cicsdev async credit-card -- for `ZWB` found no file, 2026-10-20), so nothing is refused that was proven and there is nothing to prove for NOZWB (#4702).
- **The oracle** (GnuCOBOL 3.1.2 `-std=ibm`, measured 2026-10-07 with `test_det_programs` probes): `E PIC
  ZZZ,ZZ9.99` holding 1500 (`  1,500.00`) is neither greater than `1499.99` nor `1499` -- text, not value. A literal
  is its characters as written: `0012` is `0012`, `12` is `12` (`  12` = `12` is false), `1499.99` is `149999`,
  `0.12` is `012`. A zoned item is its bytes with an overpunched sign unpunched; a packed or binary item its value in
  its PICTURE's digits (refused by the port, below) (`S9(4) COMP-3` 12 is `0012`); the sign is dropped (-1234 equals `1234`). ZERO against an
  edited item is a run of `0` characters. EVALUATE subjects, THRU ranges and an 88 on an edited item compare the
  same way.
- **A group** (#4671; `GRPCMP`, measured 2026-10-17): GnuCOBOL compares a group holding `0012` with a number as text,
  as an alphanumeric item: `= 12` is false, `= 0012` true, `> 12` false; with `N4` 12 (`0012`) true, with a `9(2)` 12
  false, with `S9(4)` -12, `S9(4) COMP-3`, `S9(4) COMP`, unsigned `COMP-3` 12 and `9(2)V99` 12 (`1200`: false) as their
  digits, sign dropped. That is IBM's rule (the numeric operand as an unsigned integer, ZWB), so no new difference:
  the five differing shapes below hold for a group as well and are refused by name.
- **Where they differ.** A signed literal: the oracle compares its sign character (`+1234` equals `+1234`, not
  `1234`), IBM moves no sign. A SIGN SEPARATE item: the oracle compares its sign character (`-1234`), IBM drops it.
  A P-scaled item: the oracle compares its stored digits (`99PP` holding 1200 is `12`), IBM drops the sign and its characters are not
  documented. An arithmetic expression against a nonnumeric item: the oracle compares its result as text of its own
  making (`  12` is not `10 + 2`, `1234` is `1000 + 234`), IBM rejects it (no table entry). A non-integer literal or
  item: IBM rejects the program; the oracle's digits (point dropped) are modelled, since a program IBM compiles
  never reaches them -- except an equality (`=`, `NOT =`, an EVALUATE WHEN, an 88 VALUE) of a numeric-edited item
  with a literal of more decimal places than the item's: cobc decides it when it compiles (`ZZ9` holding 125 is not
  `= 12.5` and `NOT = 12.5`, yet neither `< 12.5` nor `> 12.5`; `Z99V9` holding 112.5 is `= 112.5`, not `= 11.25`),
  so it is refused (measured 2026-10-08). A signed literal against an alphanumeric item is the same: `'12'` is not
  `+12` nor `-12`, `'+12'` is `+12`, `'-12'` is `-12` (measured 2026-10-08).
- **The det port.** The generator passes a numeric literal against a nonnumeric item as its written characters
  (`expr.NumLit` keeps the spelling; `Gen.literal_text`), the runtime (`Cobol.compare(Field, Field)`) compares a
  numeric item against an elementary nonnumeric one as its digits; the five differing shapes are holes by name
  ("... (C13)"). A group is a nonnumeric comparand too (#4671, measured 2026-10-17): `Cobol.operand` compares a
  numeric item against a group as its digits, as against an elementary one (before, as its raw bytes: a signed
  zoned item's overpunch, a packed or binary item's bytes, so `G = NP` with `G` `0012` and `NP` 12 was false in
  the port, true in the oracle). A group against a numeric literal was already its written characters.
- **Pinned** by `tests/cobol_mainframe/test_det_programs.py` (`EDCMP` and `GRPCMP` against GnuCOBOL; the refusals by name, group shapes too).
- **Packed and binary items (#4702) -- REFUSED.** IBM's table has no entry for a native numeric item (packed, binary,
  COMP-5) against an alphanumeric, edited or group operand, so IBM rejects the program, while the oracle compares the
  item's digits. The port used to follow the oracle; `Gen.digits_as_text` now refuses it by name ("IBM rejects a packed
  or binary operand there ... (C13)"), either way round, for every nonnumeric comparand (alphanumeric, numeric-edited,
  group) and in EVALUATE, THRU and 88 forms (all go through `Gen.cmp`). Floating-point items were already refused (C6).
  Nothing proven moved: `det_port.py check` over the six burned estates (CardDemo, CBSA, GenApp, zECS, DBB
  MortgageApplication, cicsdev async credit-card; 146 cases) left 146/146 ports unchanged, 2026-10-20, so no burned
  program compares a packed or binary item with a nonnumeric one. `EDCMP` and `GRPCMP` lost their packed / binary lines
  (still equal to GnuCOBOL otherwise); the refusal is pinned in `test_det_programs.py`
  (`test_a_native_numeric_item_compared_with_a_nonnumeric_one_is_refused_by_name_ibm_rejects_it`).
- **To settle.** A z/OS run of `EDCMP` (and of a signed-literal variant) would confirm the characters; `calibration`
  stays "uncalibrated" until then (#4702 Part 2).

### C14. Size errors (a zero divisor, an exponent, overflow) — the det runtime MATCHES the oracle (#4655); the oracle DIFFERS from z/OS where IBM leaves the result undefined
- **IBM** (Enterprise COBOL for z/OS 6.4 Language Reference, SC27-8713-03, "SIZE ERROR phrases", pp. 296-297,
  Table 32; re-read 2026-10-17, #4702): a size error is "when the absolute value of the result of an arithmetic
  evaluation, after decimal point alignment, exceeds the largest value that can be contained in the result field",
  "when division by zero occurs", or an exponentiation case. Table 32 (SIZE ERROR present / absent): zero raised to
  zero -- the imperative runs / "the value returned is 1, and a message is issued"; zero raised to a negative number
  -- the imperative runs / "the program is terminated abnormally"; a negative number raised to a fractional power --
  the imperative runs / "the absolute value of the base is used, and a message is issued". It applies to final
  results only. A binary receiver's limit is its PICTURE's, whatever TRUNC says. Rounding is done before the check.
  With ON SIZE ERROR "the value of the resultant identifier affected by the size error is not altered", the phrase
  runs and NOT ON SIZE ERROR is ignored. Without it "truncation rules apply and the value of the affected resultant
  identifier is computed". The manual states no result for a zero divisor without the phrase (no abend, no value); the
  S0CB abend on z/OS is not in the text and stays unverified.
- **Where the oracle differs from that text** (no cobc option changes either): `0 ** -n` without the phrase ends the
  program on IBM and stores 0 in the oracle (with the phrase both raise it); a negative base to a fractional power
  without the phrase uses the absolute base on IBM and leaves the receiver unchanged in the oracle. The port follows
  the oracle for both, so a scenario reaching them is outside the proofs; none does (see Reached).
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
  (`(F / FZ) * 3` is unchanged but `(F / FZ) * C`, `FM * (F / FZ)` store 0, `2 - (F / FZ)` stores 2), so
  `Hfp.divideNested` stops the run with an ArithmeticException, a named stop rather than a guess. Replaying that
  plan was tried and rejected (#4687, measured 2026-10-17): the oracle runs the OSVS alignment on EVERY intermediate
  of a float expression with two or more operations, a float receiver counting as one with places, so it truncates
  integers too (`G = C + C + C` is 3 and `G = F * C * C` is 0 with C = 3, F = 7, where the det port and z/OS give 9
  and 63; `C + F / FZ + C` is 3, `C + C + F / FZ` is 0). A replay confined to the NaN would match some shapes and
  differ on others, and one that copied the plan would reproduce an oracle artifact IBM does not have, so the stop stays.
  The same truncation makes any float expression of 3 or more operands a case where
  the oracle and z/OS differ even without a zero divisor.
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
  which IBM calls a size error and the oracle (and so the port) computes as 0, and a negative base to a fractional
  power, where IBM uses the absolute base.
- **Reached.** Not known to be: no proven scenario divides by zero or raises a size error from an exponent.
- **To settle.** A z/OS run of the shapes in `test_det_size_error.py` without ON SIZE ERROR, above all the zero
  divisor, which the manual leaves unstated.

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

### C17. INITIALIZE ... REPLACING of a table — GnuCOBOL sets the first occurrence and copies it over the others (#4892)
- **IBM.** With the REPLACING phrase, INITIALIZE sets only the elementary items of the categories named; every other
  item keeps its value (Enterprise COBOL for z/OS Language Reference, INITIALIZE statement: "the REPLACING phrase ...
  only for items of the category specified"). That holds for each occurrence of a table.
- **The oracle.** GnuCOBOL 3.1.2 sets a table's first occurrence and copies it over the others, so an item of a
  category REPLACING does not name takes the first occurrence's value in every other occurrence. Measured
  (tests/cobol_mainframe/test_det_programs.py, #4892): after `MOVE 31 TO G-T(2)`, `INITIALIZE G REPLACING
  ALPHANUMERIC BY 'XY'` left the port's `G-T(2)` at 31, as IBM says, and GnuCOBOL's at the first occurrence's 00.
- **Guarded (#5278).** The translator follows IBM (only the named categories are set, per occurrence) and, for each item
  of a category the statement does not name, emits `Cobol.sameBytes(first, occurrence k)` before it, throwing `Hole` by
  name when an occurrence differs. Where they agree, IBM's "left as it is" and the oracle's copy are the same bytes, so
  no proof rests on the oracle's copy. A table nested in a table, with such items, is still a named hole
  (test_det_initialize_replacing.py; INITRTB and INITREPL prove the agreeing case against GnuCOBOL).

### C18. LE, Db2 and CICS runtime options: each judged by one table, refused by name or a declared difference (#4707)
- **What.** The estate options file (`tests/equivalence/estate_options/<corpus>.json`, #4704) records the Language
  Environment, Db2 and CICS options an estate runs under, each with provenance, and the evidence fingerprint hashes
  them. Until #4707 nothing acted on them: a customer whose Db2 uses `DATE(USA)` or `TRAP(OFF)` would have been proven
  under ISO dates and trapped exceptions with the file saying otherwise. `runtime_options.RUNTIME_OPTION_TABLE` now
  holds one row per option; `EffectiveOptions.unhonoured_runtime` resolves the estate's values against it, and the
  oracle (`equivalence_common.compile_options` / `option_differences`) refuses or declares exactly as it does for the
  compile options (C5). An option the table has no row for is refused by name, and the options-file schema check
  fails on one, so a new estate file cannot record an option nothing has judged.
- **Provisional policies (owner to confirm).** Like C5's, these are choices from the documentation, not measurements:
  `TRAP` and `ABTERMENC` refused outside the default, Db2 `DATE` / `TIME` / `DEC` / `DECPT` refused outside the values
  the Db2 cases run with, `STORAGE` and the EBCDIC / local CCSIDs declared. All twelve cells the burned estates
  record resolve (none refuses); STORAGE is assumed in every one of them (no CEEOPTS / CEEUOPT in any burned corpus).
- **Calibration (#4702).** A z/OS probe corpus must run under the same effective options, so a measured IBM result is
  tied to the options it held under: a `z/OS-measured` rule of `cobolrt_rules.json` carries `calibrated_under`, the
  option paths above with the values the measurement ran with (`runtime_options.calibration_problems`, checked by
  `cobolrt_rules.py --check`). Every option the table judges must be stated; a value the harness cannot honour (TRAP(OFF),
  DATE(USA) ...) is named, because a measurement taken there does not calibrate a proof run without it. No rule is
  `z/OS-measured` yet, so no burned program exercises the hook.

### Runtime options: the table (#4707)
One row per option, the same four answers as C5's table. Rendered from `RUNTIME_OPTION_TABLE`; the keys are the options
file's paths.

| option | (1) changes results? | (2) cobc | (3) det port | (4) otherwise | register |
|---|---|---|---|---|---|
| `le.runtime_options.STORAGE` (IBM default `NONE,NONE,NONE,0K`) | yes: STORAGE(heap-init, stack-init, ...) decides what WORKING-STORAGE with no VALUE clause holds; a run that reads none is IBM's, and one that does is register L3's assumption | GnuCOBOL's own initial storage | same | NONE,NONE,NONE,0K honoured; any other is a declared difference (applied: GnuCOBOL's initial storage (spaces; zeros in a numeric DISPLAY item)) | C18 |
| `le.runtime_options.TRAP` (IBM default `ON,SPIE`) | yes: TRAP(OFF) leaves a program exception untrapped (the run continues past it, undefined); the oracle and the det port both end the run on one | none | none | any value but ON,SPIE, ON,NOSPIE, ON refused by name | C18 |
| `le.runtime_options.ABTERMENC` (IBM default `ABEND`) | yes: ABTERMENC(RETCODE) ends an unhandled condition with a return code instead of an abend; the harness compares the abend | none | none | any value but ABEND refused by name | C18 |
| `le.source.CEEOPTS` (IBM default ``) | no: the CEEOPTS member is only a carrier: what it sets is read into the le.runtime_options rows, each judged | none needed | -- | recorded only | C18 |
| `le.source.CEEUOPT` (IBM default ``) | no: the CEEUOPT module is only a carrier: what it sets is read into the le.runtime_options rows, each judged | none needed | -- | recorded only | C18 |
| `le.source.CEEDOPT` (IBM default ``) | no: the CEEDOPT installation default is only a carrier: what it sets is read into the le.runtime_options rows, each judged | none needed | -- | recorded only | C18 |
| `db2.format.DATE` (IBM default `ISO`) | yes: DATE(USA|EUR|JIS|LOCAL) changes the string of every date a program fetches or compares; the Db2 cases run in ISO | none | none | any value but ISO refused by name | C18 |
| `db2.format.TIME` (IBM default `ISO`) | yes: TIME(USA|EUR|JIS|LOCAL) changes the string of every time a program fetches or compares; the Db2 cases run in ISO | none | none | any value but ISO refused by name | C18 |
| `db2.format.DEC` (IBM default `15`) | yes: DEC(31) widens the precision of decimal arithmetic in SQL; the Db2 cases run in DEC(15) | none | none | any value but 15 refused by name | C18 |
| `db2.format.DECPT` (IBM default `.`) | yes: DECPT(,) makes the decimal point of SQL literals a comma; the Db2 cases run with a period | none | none | any value but . refused by name | C18 |
| `db2.ccsid.EBCDIC_CCSID` (IBM default `37`) | yes: the Db2 subsystem's EBCDIC CCSID is the code page of character columns; the proof runs the case's data in its data_encoding | none: the oracle runs the case's data in its data_encoding | same | 37, 1140 honoured; any other is a declared difference (applied: data in the case's data_encoding) | C18 |
| `db2.ccsid.SQLCCSID` (IBM default `NO`) | yes: SQLCCSID(YES) passes SQL host text in the CCSID of the program's source; the harness does not model the conversion | none | none | any value but NO refused by name | C18 |
| `db2.bind.ISOLATION` (IBM default `CS`) | no: isolation only matters between concurrent units of work; a proof runs one (the value is judged, BIND_OPTIONS) | none needed | -- | recorded only | C18 |
| `db2.bind.CURRENTDATA` (IBM default `NO`) | no: CURRENTDATA only decides lock avoidance between concurrent units of work (the value is judged, BIND_OPTIONS) | none needed | -- | recorded only | C18 |
| `db2.bind.DYNAMICRULES` (IBM default `RUN`) | no: DYNAMICRULES decides authorization and the qualifier of dynamic SQL, not a computed value (the value is judged, BIND_OPTIONS) | none needed | -- | recorded only | C18 |
| `db2.bind.VALIDATE` (IBM default `RUN`) | no: VALIDATE only decides when a missing object is reported (the value is judged, BIND_OPTIONS) | none needed | -- | recorded only | C18 |
| `db2.bind.ACTION` (IBM default `REPLACE`) | no: ACTION is a bind administration choice | none needed | -- | recorded only | C18 |
| `db2.bind.packages` (IBM default `none`) | no: the package list names where a bound program lives, not what it computes | none needed | -- | recorded only | C18 |
| `db2.precompile.PARM` (IBM default ``) | no: the precompiler PARM is judged token by token (PRECOMPILE_OPTIONS): a listing or delimiter token changes no result, one that changes SQL text, dates, decimals or code pages is refused by name | none needed | -- | recorded only | C18 |
| `db2.precompile.coprocessor` (IBM default ``) | no: how SQL reaches the compiler (precompiler or integrated coprocessor) is a build route; the det translator reads the SQL statements themselves | none needed | -- | recorded only | C18 |
| `cics.region.LOCALCCSID` (IBM default `37`) | yes: LOCALCCSID is the region's code page for EBCDIC <-> client conversion; the proof runs the case's data in its data_encoding | none: the oracle runs the case's data in its data_encoding | same | 37, 1140 honoured; any other is a declared difference (applied: data in the case's data_encoding) | C18 |
| `cics.region.CICS_TS` (IBM default ``) | no: the CICS release is recorded for provenance; the command spec (X-series) states what is modelled | none needed | -- | recorded only | C18 |
| `cics.region.DB2CONN` (IBM default ``) | no: whether the region connects to Db2 is a deployment fact; the Db2 cases name their own tables | none needed | -- | recorded only | C18 |
| `cics.translator.options` (IBM default ``) | no: translator options (CICS, SP, EDF ...) are read from the source it was given; EXEC CICS commands are refused or modelled by the CICS spec | none needed | -- | recorded only | C18 |
| `cics.program_definition.CONCURRENCY` (IBM default `QUASIRENT`) | no: THREADSAFE only matters between concurrent tasks; a proof runs one | none needed | -- | recorded only | C18 |
| `cics.program_definition.EXECKEY` (IBM default `USER`) | no: EXECKEY decides storage protection, not a computed value | none needed | -- | recorded only | C18 |

### Which burned estates exercise each judged option (#4707)
The options above that refuse or declare, and the burned estates whose COBOL holds the construct the option changes
(`runtime_options.RUNTIME_USED_BY`; a test greps the corpora, except STORAGE, which register L3 names: CardDemo READACCT,
CBSA CRDTAGY1-5). `none` means no burned program depends on the assumed value: the refusal protects a customer's
estate, and the burned estates are unaffected by it. Matching is by construct, not by reach: a corpus listed has the
statement, whether or not a proven case runs it. TRAP lists the corpora with a `DIVIDE` / `COMPUTE`; ABTERMENC those
with `EXEC CICS ABEND` or `CEE3ABD`; DATE / TIME a `CURRENT DATE` / `CURRENT TIME` or a DATE / TIME column; DEC a
SQL `DECIMAL(16..31)`; DECPT a decimal-point SQL literal; the CCSID rows any `EXEC SQL` / `EXEC CICS`.

| option | burned estates |
|---|---|
| `le.runtime_options.STORAGE` | aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa |
| `le.runtime_options.TRAP` | aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa, cics-genapp, dbb-mortgage-application, zecs |
| `le.runtime_options.ABTERMENC` | aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa, cics-genapp, dbb-mortgage-application |
| `db2.format.DATE` | aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa |
| `db2.format.TIME` | none: no burned program depends on it |
| `db2.format.DEC` | none: no burned program depends on it |
| `db2.format.DECPT` | none: no burned program depends on it |
| `db2.ccsid.EBCDIC_CCSID` | aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa, cics-genapp, dbb-mortgage-application |
| `db2.ccsid.SQLCCSID` | aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa, cics-genapp, dbb-mortgage-application |
| `cics.region.LOCALCCSID` | aws-mainframe-modernization-carddemo, cics-async-api-credit-card-application-example, cics-banking-sample-application-cbsa, cics-genapp, dbb-mortgage-application, zecs |


### CICS translator options, judged one by one (#4707)
The options file records the translator options as one string (`CICS('SP,EDF') via the program's CBL card`);
`runtime_options.translator_tokens` splits it, and each token meets `TRANSLATOR_OPTIONS`. A token with no row, and one
that changes the generated code or data layout (COBOL2, COBOL3, GRAPHIC, NATLANG), is refused by name. Rendered from
`TRANSLATOR_OPTIONS`.

| option | (1) changes results? | (4) otherwise |
|---|---|---|
| `cics.translator.CICS` | no: selects the translator's CICS command set; the default for a CICS program | recorded only |
| `cics.translator.SP` | no: the system-programming command set is read from the source it was given | recorded only |
| `cics.translator.EDF` | no: EDF only adds debugging-transaction hooks around each command | recorded only |
| `cics.translator.NOEDF` | no: NOEDF removes the debugging-transaction hooks; no result depends on them | recorded only |
| `cics.translator.DEBUG` | no: DEBUG only adds debugging-tool hooks | recorded only |
| `cics.translator.NODEBUG` | no: NODEBUG removes debugging-tool hooks | recorded only |
| `cics.translator.FLAG` | no: FLAG chooses which translator messages are listed | recorded only |
| `cics.translator.SOURCE` | no: a listing option | recorded only |
| `cics.translator.NOSOURCE` | no: a listing option | recorded only |
| `cics.translator.XREF` | no: a listing option | recorded only |
| `cics.translator.NOXREF` | no: a listing option | recorded only |
| `cics.translator.APOST` | no: the delimiter the translator writes into its own generated text | recorded only |
| `cics.translator.QUOTE` | no: the delimiter the translator writes into its own generated text | recorded only |
| `cics.translator.CPSM` | no: adds the CICSPlex SM command set | recorded only |
| `cics.translator.COBOL2` | yes: COBOL2 changes the layout of the generated working storage; not modelled | refused by name |
| `cics.translator.COBOL3` | yes: COBOL3 changes the layout of the generated working storage; not modelled | refused by name |
| `cics.translator.GRAPHIC` | yes: GRAPHIC changes how DBCS literals in commands are read; not modelled | refused by name |
| `cics.translator.NATLANG` | yes: NATLANG changes the language of messages the generated code issues; not modelled | refused by name |


### Db2 precompiler PARM, judged token by token (#4707)
The options file records the precompiler PARM as one string (`HOST(IBMCOB),XREF,SOURCE,FLAG(I),APOST`);
`runtime_options.precompile_tokens` splits it into `NAME` / `NAME(arg)`, and each token meets `PRECOMPILE_OPTIONS`. A
token with no row, and one that changes SQL text, dates, decimals or code pages with an argument other than the IBM
default the harness runs under, is refused by name. Burned estates: only CardDemo records a PARM (all five tokens are
no-effect or at the honoured default); CBSA, GenApp and DBB use the integrated coprocessor, CICS-async and zECS record
none. Rendered from `PRECOMPILE_OPTIONS`.

| option | (1) changes results? | (4) otherwise |
|---|---|---|
| `db2.precompile.PARM.HOST` | yes: HOST names the host language whose declarations the precompiler reads; only COBOL is modelled | refused by name unless IBMCOB, COBOL |
| `db2.precompile.PARM.APOST` | no: the delimiter the precompiler writes into its own generated COBOL | recorded only |
| `db2.precompile.PARM.QUOTE` | no: the delimiter the precompiler writes into its own generated COBOL | recorded only |
| `db2.precompile.PARM.XREF` | no: a listing option | recorded only |
| `db2.precompile.PARM.NOXREF` | no: a listing option | recorded only |
| `db2.precompile.PARM.SOURCE` | no: a listing option | recorded only |
| `db2.precompile.PARM.NOSOURCE` | no: a listing option | recorded only |
| `db2.precompile.PARM.FLAG` | no: FLAG chooses which precompiler messages are listed | recorded only |
| `db2.precompile.PARM.LINECOUNT` | no: a listing option (lines per page) | recorded only |
| `db2.precompile.PARM.ONEPASS` | no: how many passes the precompiler makes over the source | recorded only |
| `db2.precompile.PARM.TWOPASS` | no: how many passes the precompiler makes over the source | recorded only |
| `db2.precompile.PARM.APOSTSQL` | no: the Db2 default: the apostrophe delimits an SQL string | recorded only |
| `db2.precompile.PARM.QUOTESQL` | yes: QUOTESQL swaps the SQL string and delimited-identifier delimiters, so SQL text is read differently | refused by name unless never |
| `db2.precompile.PARM.DATE` | yes: DATE decides the format of every date string; only ISO is modelled (db2.format.DATE) | refused by name unless ISO |
| `db2.precompile.PARM.TIME` | yes: TIME decides the format of every time string; only ISO is modelled (db2.format.TIME) | refused by name unless ISO |
| `db2.precompile.PARM.DEC` | yes: DEC(31) changes decimal arithmetic precision; only DEC(15) is modelled (db2.format.DEC) | refused by name unless 15, 15. |
| `db2.precompile.PARM.DECPT` | yes: DECPT decides the decimal point of SQL literals; only the period is modelled (db2.format.DECPT) | refused by name unless ., PERIOD |
| `db2.precompile.PARM.CCSID` | yes: CCSID decides the code page of SQL character data; see db2.ccsid.EBCDIC_CCSID | refused by name unless 37, 1140 |
| `db2.precompile.PARM.STDSQL` | yes: STDSQL(YES) changes SQLCODE / SQLSTATE handling and host-variable rules; not modelled | refused by name unless NO |
| `db2.precompile.PARM.SQL` | yes: SQL(ALL) changes which SQL statements the precompiler accepts; not modelled | refused by name unless DB2 |
| `db2.precompile.PARM.GRAPHIC` | yes: GRAPHIC changes how DBCS literals in SQL are read; not modelled | refused by name unless never |


### Language Environment options, judged for syntax (#4707)
The three `le.runtime_options` rows above keep their outcome for a well-formed value (honoured, declared or refused as
stated). A value that is not Language Environment syntax at all is not one IBM accepts, so it is refused by name rather
than declared (STORAGE) or blamed on TRAP(OFF) / RETCODE. A short STORAGE spelling such as `NONE` is well-formed but is not the table's full default
spelling, so it stays a declared difference. The grammar is the LE Programming Reference's, accepted narrowly: anything
not clearly in it is refused. Burned estates: every recorded cell (`NONE,NONE,NONE,0K`, `ON,SPIE`, `ABEND`) is
well-formed and resolves as before. Rendered from `LE_OPTIONS`.

| option | syntax accepted | otherwise |
|---|---|---|
| `le.runtime_options.STORAGE` | up to four comma-separated fields: allocated-storage init, freed-storage init, stack init (each NONE or a two-digit hex byte), reserve size (digits, optional K); an omitted field is allowed | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `le.runtime_options.TRAP` | ON or OFF, optionally followed by SPIE or NOSPIE | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `le.runtime_options.ABTERMENC` | ABEND or RETCODE | a value outside this syntax is refused by name; a well-formed one is judged by the row above |


### Db2 format and CCSID options, judged for syntax (#4707)
The six `db2.format.*` and `db2.ccsid.*` rows above keep their outcome for a well-formed value (ISO, 15, a period and NO
honoured; USA, EUR, 31, a comma and YES refused; an EBCDIC CCSID declared or honoured). A value that is not Db2 syntax at
all is not one IBM accepts, so it is refused by name rather than blamed on the format it resembles or declared as a
CCSID. Burned estates: every recorded cell (`ISO`, `15`, `.`, `NO`, a plain CCSID) is well-formed and resolves as before.
Rendered from `DB2_OPTIONS`.

| option | syntax accepted | otherwise |
|---|---|---|
| `db2.format.DATE` | ISO, USA, EUR, JIS or LOCAL | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `db2.format.TIME` | ISO, USA, EUR, JIS or LOCAL | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `db2.format.DEC` | 15 or 31, optionally followed by a period | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `db2.format.DECPT` | a period or a comma, or PERIOD or COMMA | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `db2.ccsid.SQLCCSID` | YES or NO | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `db2.ccsid.EBCDIC_CCSID` | a CCSID: one to five digits, not zero | a value outside this syntax is refused by name; a well-formed one is judged by the row above |


### CICS region and program-definition options, judged for syntax (#4707)
`cics.region.LOCALCCSID` keeps its outcome for a well-formed value (37 and 1140 honoured, another CCSID declared); the
other rows below are recorded only for a well-formed value. A value that is not CICS syntax is not one IBM accepts, so it
is refused by name rather than declared as a code page. Burned estates: every recorded cell (`037`, `YES`, `4.2`,
`THREADSAFE`) is well-formed and resolves as before. `cics.translator.options` is judged token by token above. Rendered
from `CICS_OPTIONS`.

| option | syntax accepted | otherwise |
|---|---|---|
| `cics.region.LOCALCCSID` | a CCSID: one to five digits, not zero | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `cics.region.DB2CONN` | YES or NO | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `cics.region.CICS_TS` | a release number: digits and periods, such as 4.2 or 5.6 | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `cics.program_definition.CONCURRENCY` | QUASIRENT, THREADSAFE or REQUIRED | a value outside this syntax is refused by name; a well-formed one is judged by the row above |
| `cics.program_definition.EXECKEY` | USER or CICS | a value outside this syntax is refused by name; a well-formed one is judged by the row above |


### Db2 bind options, judged per value (#4707)
The four bind options that carry a value are checked against what IBM accepts for them; a value outside the set is
refused by name (the rows above stay "recorded only" for an accepted value, so a z/OS measurement need not state them).
`ACTION` and `packages` are bind administration and stay recorded for any value. Burned estates: CardDemo records
ISOLATION CS and CURRENTDATA YES, CBSA ISOLATION UR, GenApp ISOLATION CS, CURRENTDATA NO, DYNAMICRULES BIND and VALIDATE
BIND; CICS-async, DBB and zECS record none. No burned program issues dynamic SQL or a `WITH UR/CS/RR/RS` clause, so no
accepted value changes a burned result. Rendered from `BIND_OPTIONS`.

| option | (1) changes results? | (4) otherwise |
|---|---|---|
| `db2.bind.ISOLATION` | no: a proof runs one unit of work, and a program sees its own updates at every isolation level | recorded only for CS, UR, RR, RS; any other value refused by name |
| `db2.bind.CURRENTDATA` | no: CURRENTDATA only decides lock avoidance and block fetch between concurrent units of work | recorded only for YES, NO; any other value refused by name |
| `db2.bind.DYNAMICRULES` | no: RUN and BIND only change the authorization and qualifier of dynamic SQL, which no burned program issues; DEFINE* and INVOKE* take a routine owner's context, which is not modelled | recorded only for RUN, BIND; any other value refused by name |
| `db2.bind.VALIDATE` | no: VALIDATE only decides when a missing object is reported; a program that ran found every object | recorded only for RUN, BIND; any other value refused by name |


### CICS conventions the ports rely on: EIB fields and abends (#4707)
Not options-file keys: facts of the run a program reads. The same four answers; the register column names the entry that
states each (`none (gap)`: no entry does). Only fields a burned corpus's COBOL names have a row; `EIBCPOSN`, `EIBREQID`,
`EIBRSRCE`, `EIBERR` / `EIBERRCD` are X64's unmodelled, refused-by-name fields. Rendered from `CICS_CONVENTIONS`.

| convention | (1) changes results? | (2) cobc | (3) det port | (4) otherwise | register |
|---|---|---|---|---|---|
| `cics.convention.EIBCALEN` | yes: the length of the COMMAREA the task started with; programs branch on 0 | the stub's WS-LEN | the runner-stated COMMAREA length | a reference past EIBCALEN is refused by name | X23, X10 |
| `cics.convention.EIBAID` | yes: the key pressed selects the screen path | the case's AID name, moved by the stub | the case's AID name; HANDLE AID reads it | a task started without a terminal has none (IBM is silent): not read | X16, X27 |
| `cics.convention.EIBRESP` | yes: the numeric condition of the last command | the stub's GG-RESP | the runtime's response code | a command or condition IBM leaves open is refused by name | X28, X21 |
| `cics.convention.EIBRESP2` | yes: the reason code of the last command | the stub's GG-RESP2 | the runtime's reason code | a reason code IBM does not document is refused by name | X28, X21 |
| `cics.convention.EIBTASKN` | yes when a program stores or compares it | the stub's $GGCICS_TASKN | the runner-stated task number | DIFFERS from z/OS in value, both sides agree (declared) | X21 |
| `cics.convention.EIBTRNID` | yes: the transaction id a program routes on | the case's transid, moved by the stub | task.transid() | the case's transid, ASSUMED to be the region's; not validated (X68) | X68 |
| `cics.convention.EIBTRMID` | yes when a program starts a task at its own terminal | the case's termid, moved by the stub | task.termid(), blanks for a task with none | ASSUMED | X18 |
| `cics.convention.EIBDS` | yes when a program reads the last data set referred to | set before a file control command | set before a file control command, only in a program that reads it | ASSUMED | X64 |
| `cics.convention.EIBRCODE` | yes: the six-byte response code | none | none | unmodelled: a program that reads it is refused by name | X64 |
| `cics.convention.EIBFN` | yes: the code of the last command | none | none | unmodelled: a program that reads it is refused by name | X64 |
| `cics.convention.ABEND.ABCODE` | yes: the four-character abend code is compared | the stub's abend code | the runtime's abend code | a code IBM does not state (an unknown mapset: ABM0) is ASSUMED | X31, X5 |
| `cics.convention.ABEND.HANDLE_ABEND` | yes: a handled abend continues in the program's routine | modelled by the stub | modelled by the runtime | forms IBM leaves open are refused by name | X16, X5 |
| `cics.convention.ABEND.UNHANDLED` | yes: the task ends with the abend | the harness compares the abend | the harness compares the abend | ABTERMENC(RETCODE) is refused by name (le.runtime_options.ABTERMENC) | C18 |

### C19. ALTER — the altered GO TO reads a per-paragraph slot: MODELLED; independent segments and non-lone-GO-TO paragraphs REFUSED
- **IBM** (Enterprise COBOL for z/OS 6.4 Language Reference, ALTER statement): the ALTER statement changes the
  transfer point specified in a GO TO statement. ALTER is an obsolete element, but supported. The paragraph named
  (procedure-name-1) must contain only one sentence, and that sentence must be a GO TO statement without the DEPENDING
  phrase. The transfer point set by ALTER lasts until the next ALTER of that paragraph; in an independent segment the
  altered GO TO returns to its initial state each time the segment is entered. The printed manual's page numbers are
  not recorded here; the section is the reference.
- **The port** (`det/stmt.py`, `det/gen.py`, the paragraph dispatcher). An ALTER is parsed with all its
  `p TO [PROCEED TO] q` pairs. Each altered paragraph gets a Java `int` slot (`alt<i>`), initialised to the target its
  own GO TO names; the altered GO TO returns `GOTO | slot` and ALTER writes the slot. The last ALTER wins, and GO TO,
  PERFORM and fall-through reach the paragraph as any other, so they see the same slot.
- **Refused by name** (a hole; the rest of the program still translates): an ALTER of a paragraph that is not a lone
  GO TO without DEPENDING (`ALTER p: the paragraph is not a lone GO TO without DEPENDING (IBM, ALTER)`), and an ALTER
  of an undeclared paragraph.
- **Not modelled.** An independent segment (section priority 50 or above / SEGMENT-LIMIT), where the altered GO TO
  resets on entry; no burned program uses one. A bare `GO TO.` with no operand, reached before any ALTER, throws a
  Hole at run time (IBM leaves the target undefined).
- **Reached.** Yes: `tests/cobol_mainframe/test_det_programs.py` ALTER1 (several ALTERs of one paragraph, a multi-pair
  ALTER) and ALTER2 run as the port and under GnuCOBOL `-std=ibm` and compare. CardDemo CBSTM03A, the only burned
  program with ALTER, goes from 9 holes to 5; the rest are `SET ADDRESS OF` over system control blocks.

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
  character and encodes back to that byte. A byte whose character a lower byte already has (IBM037 and its
  siblings decode both X'15' and X'25' to U+000A; the round trip used to write X'25' as X'15') reads as a private-use
  character (U+E000 + the byte) and encodes back to its own byte (#4702). GnuCOBOL writes the same raw bytes.
- **A multi-byte record charset refuses (#4702).** UTF-8 cannot hold X'80'..X'FF' alone as text (they are not a
  sequence it decodes), so `Cobol.hex` refuses such a literal by name (`UnsupportedOperationException`, "is not valid text
  in the record charset") instead of writing U+FFFD's three bytes; a sequence it does decode (X'C3A9') is kept. No
  burned estate runs a multi-byte record charset, so no port moves. Pinned: `test_det_sysout_bytes_4702.py` (all 256
  values under ISO-8859-1, IBM037, IBM1047, windows-1252 and UTF-8; the LF after a DISPLAY and none after WITH NO
  ADVANCING, in the batch and the standalone Sysout).
- **The line separator is framing, not data (#4698).** IBM: without WITH NO ADVANCING, "after the last operand has been
  transferred to the output device, the positioning of the output device will be reset to the leftmost position of the
  next line" (Language Reference, DISPLAY statement). That is a record boundary on z/OS, not a byte in the record: a
  DISPLAY to SYSOUT writes a record of the item's bytes; there is no newline byte. Our SYSOUT capture needs a separator, so the Sysout (batch and standalone) writes a
  plain LF (0x0A, as cobc does) after each DISPLAY in every record charset, not the charset's encoding of `"\n"`
  (0x15 / 0x25 on EBCDIC). The harness compares records: it splits both captures on the LF byte, then decodes each
  record (`equivalence_common.sysout_lines` / `compare_sysout`).

- **Audit against IBM (#4702).** The IBM side is quoted, not assumed.
  - **Hex literal.** "Two hexadecimal digits represent one character in a single-byte character set (EBCDIC or
    ASCII)"; "The DBCS compiler option has no effect on the processing of hexadecimal notation of alphanumeric
    literals" (Language Reference, "Hexadecimal notation for alphanumeric literals"). So `X'40'` is the byte 0x40 and
    nothing translates it: MATCHED, the oracle (cobc writes the raw byte), the port and IBM agree.
  - **Ordinary literal.** "Basic alphanumeric literals can contain any character in a single-byte EBCDIC character
    set" (same chapter): its bytes depend on the compiler's CODEPAGE (C5). The port encodes it by the record charset;
    that is the characters DIFFERS above, not a new difference.
  - **Declared oracle-vs-IBM difference: the separator.** IBM ends a DISPLAY record at the device; cobc writes LF. The
    port writes LF so the capture can be split; the comparator splits on it and compares records, so the difference
    never reaches a verdict. The LF is not IBM's, and nothing in a program can read it.
  - **Checked against the oracle (#4702).** `test_det_bytes_4690.py::test_batch_sysout_low_bytes_equal_gnucobols`
    runs `MOVE X'hh' TO R` / `DISPLAY R` for X'00'..X'7F' (X'0A' aside: it is the capture's separator) under
    ISO-8859-1, IBM037, IBM1047 and windows-1252, in the bytes, typed and groups modes, and compares with cobc byte
    for byte. It found one divergence, fixed here: under IBM037 the Sysout (batch and standalone) encoded the
    private-use character `Lossless` gives X'25' as `?` (0x3F), because it used the plain charset. The Sysout now
    maps U+E000..U+E0FF back to their byte. `test_det_sysout_bytes_4702.py` pins X'1525' through both Sysouts.
  - **Not modelled, ASSUMED (no burned program reads it).** The Language Reference gives the system output device a
    default logical record size of 120 characters, padded with spaces ("the remaining rightmost positions are padded
    with spaces"), and a maximum of 255. Neither side pads or splits a DISPLAY to that size, so a record longer or
    shorter than the device's is not compared as IBM would write it. The burned sources (CardDemo, CBSA, DBB
    MortgageApplication; GenApp, zECS and the async credit-card sample have no DISPLAY) hold no DISPLAY source line over
    100 characters; the summed length of a multi-operand DISPLAY's fields was not computed, so the bullet stays ASSUMED. Pending z/OS calibration (#4702 part 2).
  - Rules: `RT-CBL-HEX-LITERAL-BYTES`, `RT-DATA-BYTE-TRANSPARENT`, `RT-SYS-DISPLAY-SYSOUT`
    (`docs/language_status/cobolrt_rules.json`), all `uncalibrated`.

### D3. Zoned signs in ASCII data — MATCHED
- `-fsign=EBCDIC` reads the corpora's ASCII data with EBCDIC-style overpunch (`{` = +0, A–I positive, `}` J–R
  negative), as the data was unloaded from z/OS.
- **IBM.** Enterprise COBOL for z/OS 6.4 Programming Guide (SC27-8714-03), "Sign representation of zoned and
  packed-decimal data": the sign of an external decimal item is the zone nibble of its last digit (X'C' positive,
  X'D' negative, X'F' unsigned or positive under NOPFD). On the EBCDIC code page those bytes display as `{` / `A`-`I`
  (C0-C9), `}` / `J`-`R` (D0-D9). The corpora's ASCII unloads keep those characters, so `-fsign=EBCDIC` reads the
  same sign IBM would.
- **Declared difference.** An ASCII byte that is no overpunch (e.g. `!`) has no IBM meaning in these unloads; the
  oracle reads its low nibble (C11 holds the rule and what the port refuses).

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
- **IBM's table (#4702).** Enterprise COBOL for z/OS 6.4 Language Reference (SC27-8713-03), "File status key", Table 34: 00 successful; 02 duplicate alternate key
  (indexed); 10 at end (sequential READ, nothing next); 22 duplicate prime or alternate key on WRITE / REWRITE without
  DUPLICATES; 23 "randomly access a record that does not exist"; 35 is in the permanent-error row (OPEN INPUT, I-O or
  EXTEND on a nonoptional file that is unavailable). The runtime's meaning for each code is IBM's text.
- **Assumed** (the part IBM does not tabulate): that GnuCOBOL's Berkeley DB file raises each code in the same *situation*
  as VSAM does, and the ORDER of the checks when two apply (e.g. a duplicate key on a record that also sits out of
  sequence, 21 vs 22). A case that reaches such a pair is out of scope until z/OS calibrates it (#4702 part 2).
- **Not modelled.** VSAM's OPEN-time checks: 39 (attributes conflict), 04 (record length) and 97 (verified open).
  IBM defines 39 (the fixed file attributes against the program's) and 04 (a READ whose length is outside the FD's
  minimum or maximum; 00 under VLR(COMPAT)) in Table 34; 97 is VSAM's own, not in that table.

### F2. Injected faults — MATCHED
- Fault runs (`ggfault.c`, CICS `faults.cfg`) give a statement the same status or RESP on both sides, and say which
  faults fired.
- The values are the ones IBM documents for the condition (CICS TS 6.x, each command's "Conditions", for example
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-xctl and
  ibm.com/docs/en/cics-ts/6.x?topic=summary-retrieve; the file statuses are F1's Table 34, SC27-8713-03). What a real device failure would give is not modelled.
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
  IBM (Programming Guide, "Layout of format-V records"): each logical record is preceded by `cc`, 4 bytes: `ll`, 2 bytes
  "designating the logical record length (including the cc field)", and `bb`, 2 bytes reserved; the program never
  sees them.
- **Assumed.** That a record's content and length are what z/OS would write; block descriptors (BDW) and spanned
  records are not modelled. The det translator writes the same framing (`DetFiles`); before this it wrote VB records
  padded to the maximum length, which no case had exercised.

- **Audit against IBM (#4702).** The comparator needs no IBM framing: it compares the content and length of each
  record, so the 2-byte-length-plus-2-zero-bytes frame is a declared oracle-vs-IBM difference in the bytes at rest only.
  - IBM's `ll` counts its own 4 bytes (a record of 12 data bytes has `ll` = 16); `split_varseq` reads GnuCOBOL's length
    as the data length (12). Both give the same record, and nobody compares the header bytes.
  - IBM also frames each block (`CC`: `LL` + `BB`, "the first 4 bytes of each block") and, for spanned records
    (format S), each segment (a segment descriptor). None is written: the capture is a sequential file, not a QSAM block
    stream. Still ASSUMED: that a program, which cannot see these fields (the Guide: "not available for you to use"),
    cannot tell. Reached by CardDemo READACCT only.
  - Pending z/OS calibration (#4702 part 2): a VB file written on z/OS, compared record for record.

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
  reference (ibm.com/docs/en/cics-ts/6.x?topic=summary-read and the sibling command pages; EIB fields:
  ibm.com/docs/en/cics-ts/6.x?topic=reference-eib-fields), cited in the code.
- **Checked against.** The cics-crucible (210 doc-cited cells passing, v0.5.0). Not checked against a CICS region.

### X2. Screens are compared as the symbolic map — ASSUMED
- **Compared.** Each SEND MAP's symbolic map: the data, the attribute, colour and highlight subfields, and the cursor
  (length -1).
- **Not modelled.** What a 3270 shows after BMS merges the physical map, MAPONLY, DATAONLY, ERASE and FRSET. Two
  ports with equal symbolic maps could differ on a terminal only if BMS itself differed.
- **IBM.** CICS TS Application Programming Reference, EXEC CICS SEND MAP (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-map):
  SEND MAP merges the application data structure (the symbolic map) with the physical map BMS holds, and builds the
  3270 data stream; MAPONLY sends the map with no data, DATAONLY only the data, ERASE clears the screen first, and
  FRSET resets the modified-data tags. The wording is paraphrased, not verbatim.
- **Declared difference.** IBM's result is the 3270 data stream BMS builds; the oracle and the port are compared one
  step earlier, at the symbolic map, since BMS itself is not modelled.

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
- **IBM.** CICS TS Application Programming Reference, EXEC CICS SYNCPOINT and SYNCPOINT ROLLBACK
  (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-syncpoint): SYNCPOINT commits the unit of work, ROLLBACK backs
  out the changes to recoverable resources since the last syncpoint; INVREQ and ROLLEDBACK are the responses named
  above. CICS TS Recovery and Restart Guide: a file defined RECOVERY(NONE) is not backed out, and an abend that ends
  the task backs out the recoverable resources. The wording is paraphrased, not verbatim.
- **Declared difference.** Temporary storage: IBM backs out a recoverable TS queue, the models do not back out any
  (see Not modelled above).

### X4. Time — ASSUMED
- **What.** EIBDATE and EIBTIME are the case's clock at dispatch. ASKTIME leaves them unchanged (a task takes no time),
  and FORMATTIME formats from that clock.
- A DELAY takes no time either (CBSA's INQCUST and credit agencies retry after one); ENQ and DEQ are NORMAL, one
  task being the region's only one.
- **IBM.** CICS TS Application Programming Reference, EXEC CICS ASKTIME, FORMATTIME, DELAY, ENQ and DEQ
  (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-asktime): ASKTIME updates the task's current time (EIBDATE
  and EIBTIME are refreshed by it, ABSTIME is returned); FORMATTIME formats an ABSTIME; DELAY suspends the task for
  the interval; ENQ and DEQ serialize on a resource across tasks. The wording is paraphrased, not verbatim.
- **Declared difference.** IBM's ASKTIME returns a later time and a DELAY takes the interval; here neither moves the
  clock. ENQ never waits, since one task is the region's only one.

### X5. What IBM leaves open — REFUSED
Refused by name (`equivalence_cics.Unsupported`):
- HANDLE ABEND PROGRAM (X67);
- START with interval options;
- READQ TS with SET or SYSID;
- an option the stub does not know.

The length READQ TS returns on ITEMERR or QIDERR is not documented, so it is not set.

### X6. A WRITEQ LENGTH past its FROM item — ASSUMED: FROM's bytes, then spaces
- **What.** GenApp's LGSTSQ (the error logger every GenApp program LINKs on its error paths) writes
  `LENGTH(WS-RECV-LEN)`, the caller's COMMAREA length + 5. That is more than `FROM(WRITE-MSG)` holds (95 bytes) when the
  caller passes more than 90 bytes -- WRITE-ERROR-MESSAGE's second LINK passes the 99-byte CA-ERROR-MSG, so LGSTSQ
  writes 104 bytes -- and CICS copies the bytes that follow WRITE-MSG in storage.
- **Why it is an assumption.** The bytes after FROM depend on how the compiler lays out WORKING-STORAGE; GnuCOBOL's
  layout is not IBM's, so no oracle here can say what z/OS writes. **Not settled on z/OS (#4050).**
- **Modelled (ASSUMED, owner 2026-10-21).** "Owner OK (phone 2026-10-21): model short-source WRITEQ (X6: LENGTH past
  FROM) in the test stand-in/oracle, recorded as ASSUMED (IBM undefined; GnuCOBOL layout differs)". The record is FROM's
  bytes followed by SPACES (in the program's page) up to LENGTH, on both sides: the translated WRITEQ TD / TS moves FROM
  into a space-filled `GG-PADQ PIC X(32767)` and writes that; the det port calls `DetCics.padded`. LGSTSQ's 104-byte
  record is now compared, field by field, with the task's end state.
- **Still refused.** A LENGTH over 32767 (the longest record; the run stops 98, "not modelled", `DetCics.PastFrom`).
  START / PUT CONTAINER / GET CONTAINER / DOCUMENT CREATE past their area stay refused whole (`DetCics.within`).
- **History: judged up to the refusal** (owner decision on #4607, 2026-10-07; superseded by the 2026-10-21 decision
  above for a WRITEQ). A task reaching a WRITEQ past FROM used to be compared only up to that statement, with X6 listed
  among the proof's assumptions. Such a task now runs on and its end state is compared; the stub logs each padded
  WRITEQ, and the proof names X6 among the assumptions of every task that ran one (`x6_padded`, #5252).
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
- **IBM.** CICS TS Application Programming Reference, EXEC CICS ASSIGN (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-assign):
  PROGRAM returns the name of the current program; INVOKINGPROG returns the name of the program that invoked it
  (by LINK or XCTL), blanks when the program was not invoked by another one. The wording is paraphrased, not
  verbatim.
- **Declared difference.** Only a task's own LINK / XCTL chain is modelled; the other ways IBM documents a program
  being invoked (e.g. through a remote DPL) are not.

### X8. A reference modification past its item — refused by name
- **What.** GenApp's LGAPDB01 MOVEs into `WS-VARY-CHAR(1:WS-VARY-LEN)`, the COMMAREA's length less the request's:
  with the 32500 bytes its caller LGAPOL01 passes, about 28K past WS-VARY-CHAR's 3900. Compiled without SSRANGE (IBM's
  default) that overwrites whatever follows in storage; GnuCOBOL's layout is not IBM's.
- **Effect.** The det port stops (an index error), so such a scenario can never be proven by accident; the case leaves
  it out and says so. Since #4449 the COBOL oracle is compiled with `-fec=EC-BOUND-SUBSCRIPT` and `-fec=EC-BOUND-REF-MOD` (`BOUND_FLAGS` in
  `equivalence_common.py`), so a scenario that drives either past its item stops with a libcob bounds error and the
  harness refuses it by name instead of comparing storage-layout luck.
- **A subscript past its table is the same** (#4463): CardDemo COMEN01C rejects an option above 11, then still reads
  `CDEMO-MENU-OPT-USRTYPE(WS-OPTION)`; option 99 reads 4K past the record. carddemo-menu's `option-12-typed-over` sent
  99 from #4049 on, and its det port stopped there (an index error) -- the case now sends 12, inside the 12-entry
  table. The same flags now refuse such a scenario by name.
- **How a case answers it.** A CICS case must list each overrunning scenario in its `bounds_refused` (scenario ->
  reason); it is then reported as refused, never proven. An unlisted one fails the run with every overrun named. A
  derived scenario is refused without a listing. Batch and CALL runs fail with the same message.
- **A reference modification of length 0 is the one exception a case may opt into (#6072).** IBM defines it under
  `SSRANGE(ZLEN)` (APAR PI53044: the item is empty, nothing is reported) and leaves it undefined under the default
  NOSSRANGE. A case whose program does it on purpose (COTRTLIC's `WS-STRING-OUT` for a blank info message, COTRTUPC's
  9500) gives the reason in `zero_length_refmod`; the oracle is then compiled with GnuCOBOL's `ref-mod-zero-length`
  switch (`-conf=` the IBM dialect plus that line, staged as `zero-length-refmod.conf`), so length 0 is an empty item and
  a MOVE into or out of it changes nothing, as the det runtime's zero-length `Field.ref` does. **Assumption relied on:**
  that empty-item reading, applied to a program built NOSSRANGE. Every other bound check stays on (a subscript, an offset
  below 1, a length past the item is still refused by name, and still needs `bounds_refused`). Batch and CICS runs
  honour the key; CALL runs (`equivalence_call.py`) do not yet.
- **Found in the burned estates (#4449).** carddemo-cardlist: 16 scenarios (COCRDLIC line 518, subscript 0 of
  `VIEW-REQUESTED-ON`); carddemo-cotrtlic: 6 (`WS-STRING-OUT` reference-modified with length 0); carddemo-menu:
  `option-zero`, `option-blank` (subscript 0 of `CDEMO-MENU-OPT-USRTYPE`); cbsa-bnk1cac `rate-three-places` and
  cbsa-bnk1uac `rate-four-places` (`INTRTI` reference-modified past its 7 bytes). Not covered: `cics_crucible.py`
  compiles without the flags.

### X9. Named counters — MATCHED
- GET COUNTER returns the counter's value and then adds one (IBM CICS TS, GET COUNTER, ibm.com/docs/en/cics-ts/6.x?topic=summary-get-counter-get-dcounter); a counter the region does not
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
- **What IBM documents** (CICS TS 6.x, EXEC CICS STARTBR / READNEXT / READPREV, and "Sequential reading (browsing)";
  ibm.com/docs/en/cics-ts/6.x?topic=summary-readnext; wording paraphrased):
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
- **What IBM documents** (CICS TS 6.x, EXEC CICS READ, ibm.com/docs/en/cics-ts/6.x?topic=summary-read; wording paraphrased): LENGTH "specifies the length, as a halfword binary value, of
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
- **What IBM documents** (CICS TS, EXEC CICS RECEIVE (3270 logical), ibm.com/docs/en/cics-ts/6.x?topic=summary-receive-3270-logical,
  and (LUTYPE2/LUTYPE3); wording paraphrased): with INTO and no
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
- **What IBM documents** (CICS TS 6.x, EXEC CICS HANDLE AID, IGNORE CONDITION, HANDLE CONDITION, PUSH HANDLE, POP
  HANDLE; RESP and RESP2 options; ibm.com/docs/en/cics-ts/6.x?topic=summary-handle-aid, `...summary-ignore-condition`,
  `...summary-handle-condition`, `...summary-push-handle`, `...summary-pop-handle`; wording paraphrased). HANDLE AID: a key's label, taken "after the input command is completed; that is,
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
- **Refused by name, mostly where IBM is silent** (`CicsError` / `Unsupported` at translation, a DRIVER-ERROR or IllegalStateException at run
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
- **RETURN CHANNEL (#5005, EXEC CICS RETURN).** IBM: CHANNEL is "the name ... of a channel that is to be made available to
  the next program" (a channel that does not exist is created empty); COMMAREA is its alternative, and a RETURN below the
  highest logical level fails with INVREQ RESP2 2 and returns to the program. The port (`CicsTask.returnChannel`) ends the
  task with the channel recorded as `returnedChannel` and a RETURN event naming it and its containers; the translator
  refuses CHANNEL without TRANSID, and beside COMMAREA / LENGTH / IMMEDIATE (IBM does not say), by name. **Carried on the Java leg:**
  the Java runner hands the channel to the next terminal task (`pendingChannel` -> `withChannel`; none after an abend, a
  RETURN without CHANNEL or a failed RETURN), the log's RETURN event records `channel`, and the deterministic port on the
  java-ported side passes pc-return-channel carry / modify / link-level2 (`tests/cics_crucible/det-ports/`; a channel
  program has no java-facade). **Carried on the stub too:** `GGCRETC` saves the
  task's current channel as `return_channel.cfg` (the `channel.cfg` format) and ends the task, a RETURN below level 1
  logs INVREQ RESP2 2 and returns, the runner copies the file to the next terminal task's `channel.cfg`, and the
  task driver's `GGCCHIN` makes it that task's current channel. The cobol-stub cells of pc-return-channel
  (carry / modify / link-level2) pass.
- **Assumed.** A container holds the program's bytes. A BIT container is never converted; a CHAR one put and got
  with no CCSID option is in the region's CCSID both ways, so it is not converted either -- the port keeps the bytes
  in its storage's page and the stub in its own, as each side keeps every other area.
- **Code-page conversion (#4270, FROMCCSID / FROMCODEPAGE / INTOCCSID / INTOCODEPAGE / CONVERTST / CCSID).** IBM: FROMCCSID
  or FROMCODEPAGE implies DATATYPE(CHAR) ("A data-type of BIT is invalid with the FROMCCSID option": INVREQ RESP2 34);
  the container's CCSID is "the value that was specified, or defaulted, on the first PUT CONTAINER command for this
  container" (the region's, 037, when none); data put on an existing CHAR container is "converted (if required)";
  GET converts to INTOCCSID, else to "the CCSID of the region"; CONVERTST(NOCONVERT) returns the data unconverted and
  CCSID(area) "the CCSID of the data as returned under CONVERTST(NOCONVERT)" (zero for BIT); IANA names in
  FROMCODEPAGE / INTOCODEPAGE are converted to a CCSID and "the subsequent data conversion process is identical". Modelled
  for the CCSIDs 37, 500, 1140 and 1208 only. IBM lists all four as conversion CCSIDs ("Conversion CCSIDs for CICS TS",
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=reference-conversion-ccsids-cics-ts: Table 23 "037 ... ibm037", "500 ...
  ibm500", "1140 ... ibm01140 ... with euro"; Table 38 "1208 UTF-8 ... Unicode"). 37, 500 and 1140 are single-byte EBCDIC
  pages, so a conversion never changes a length; 1208 (UTF-8) is modelled for ASCII bytes only, one byte a character, so the
  length is kept there too -- a 1208 byte at or above X'80', or a character beyond ASCII converted to 1208 (a multibyte
  sequence), is refused. INTOCCSID on a BIT container is CCSIDERR RESP2 3, "The data was created with a data type of BIT" and
  "The data was returned without any code page conversion" (GET CONTAINER page): both runtimes return CCSIDERR/3 with the
  data in INTO unconverted and leave FLENGTH and CCSID(area) alone -- ASSUMED: the page says FLENGTH is set to the length of
  the data, but not whether that holds under this condition, and the case's hand-traced log does not log it either. A program's
  bytes are read as the region's page 037 (the port's convention, #4528; the translator refuses the options for a program
  whose declared page is another EBCDIC one), and a conversion is the character-to-character map between the two pages
  applied to those bytes: 500 reads seven characters of 037 differently (cent sign, broken bar, exclamation mark, not
  sign, circumflex, the square brackets), 1140 is 037 with the euro where 037 has the currency sign. The expected maps
  in `tests/cics_crucible/test_container_ccsid_4270.py` come from Python's cp037 / cp500 / cp1140 codecs, not from either
  runtime; the stub (ggcics.c, a small permutation) and CicsTask (the JDK's Cp037 / Cp500 / Cp1140) both reproduce them. A channel is in the scope of
  the level that created it and of a level it is LINKed or XCTLed to; the LINKed program's channels die with its
  level. A GET's data goes into INTO's first bytes and leaves the rest as it was; FLENGTH is set back on NORMAL and
  LENGERR only (on another condition IBM does not say).
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run
  time): BYTEOFFSET and PREPEND on a CHAR container (below); RETURN
  CHANNEL on the stub (the next task's channel: only the Java runner carries it); LINK / XCTL with both CHANNEL and COMMAREA. At run
  time: a CCSID other than 37, 500, 1140 and 1208 (IBM: CCSIDERR RESP2 1 outside the valid range, 2 for an unsupported pair; a
  real region converts many more); a CCSID 1208 byte beyond ASCII, or a character beyond ASCII converted to 1208 (multibyte:
  the length would change); a character the target CCSID lacks (037 / 500 <-> 1140: the currency sign and the euro),
  which IBM answers with CCSIDERR RESP2 4 and a blank in the converted data, without saying what FLENGTH or a PUT then do;
  INTOCCSID on a BIT container longer than INTO (whether LENGERR or CCSIDERR wins is not said) and GET CONTAINER SET with
  INTOCCSID on a BIT container (whether a block is acquired is not said);
  FROMCCSID onto an existing BIT container, with a negative FLENGTH, or with a data type and no channel in scope (INVREQ
  RESP2 1 and 2 both fit and IBM ranks neither; FROMCCSID or INTOCCSID alone with no channel is INVREQ RESP2 2, modelled); CONVERTST with INTOCCSID / INTOCODEPAGE, CCSID without
  CONVERTST(NOCONVERT) (the translator); MOVE CONTAINER onto a container of another CCSID; WEB SEND of a container in a
  CCSID other than the region's; a PUT naming the other data type for an existing container (IBM says DATATYPE "applies only to new
  containers" and also lists INVREQ RESP2 33 for "an attempt ... to change the data-type"); a channel an XCTL left
  behind (IBM's scope tables do not say); an FLENGTH past FROM / INTO, or a negative one on GET; a name that is
  blank, longer than 16, or holds a character outside IBM's set on a command whose page says nothing of one (GET /
  DELETE CONTAINER, LINK / XCTL CHANNEL, the browse and MOVE commands); a name holding & < or the not sign (RUN
  TRANSID's page allows them in a channel name, PUT CONTAINER's does not); on PUT CONTAINER, two illegal names, or an
  illegal one with a negative FLENGTH or no channel in scope (which condition IBM raises first is not documented).
- **BYTEOFFSET and PREPEND (#5005), BIT containers only.** GET CONTAINER (CHANNEL): BYTEOFFSET is "the offset in bytes where the
  data returned starts" (a fullword); "If the value specified is less than zero, zero is assumed"; "The maximum length returned is
  equal to the length of the data in the container minus the BYTEOFFSET value"; FLENGTH out is "the length of the data returned";
  an offset "greater than, or equal to, the length of the container" is LENGERR RESP2 12. PUT CONTAINER (CHANNEL), PREPEND ("6.2
  and later"): "the data passed to the container is prepended to the existing data in the container". Both runtimes
  (`CicsTask.getContainerAt` / `putContainer(.., prepend)`, `GGCGETC` / `GGCPUTC`) return the bytes from the offset, set FLENGTH
  to the length returned and put the new data in front, so a later offset sees the new layout; PREPEND on a new container is the
  data alone. ASSUMED: after LENGERR RESP2 12 FLENGTH and INTO are left as they were (the page states FLENGTH per option, not per
  condition; the cics-crucible case `ca-container-byteoffset` does not log them). REFUSED by name: BYTEOFFSET on a CHAR container
  and PREPEND with CHAR, FROMCCSID or onto a CHAR container (IBM counts the offset in the requested code page, and the
  conversion order is not said); an FLENGTH below the data left from the offset (LENGERR RESP2 11, and whether FLENGTH then holds
  the length returned or the container's is not said); BYTEOFFSET with NODATA, SET (X58), INTOCCSID, CONVERTST or CCSID(area);
  PREPEND together with APPEND (IBM does not say); at run time the stub and CicsTask refuse the data cases, the translator and
  the harness the option combinations. Reached: cics-crucible `ca-container-byteoffset` (`read`, `past-end`) passes on cobol-stub;
  `tests/cics_crucible/test_container_byteoffset_5005.py` runs offsets -2^31..2^31-1, FLENGTH equal to the data left and PREPEND on
  a new, an empty and an existing container on both runtimes line for line.
- **GET64 CONTAINER / PUT64 CONTAINER (#5005).** IBM's pages (`summary-get64-container`, `summary-put64-container`) give the
  same options, the same conditions and the same RESP2 values as GET / PUT CONTAINER (CHANNEL); FLENGTH is a fullword on both,
  and only the data area (INTO / FROM) and SET are "64-bit". **ASSUMED:** a COBOL item has no address above the bar, so INTO /
  FROM are the program's ordinary item and the command behaves as its 31-bit twin: the translator (`GET64_CONTAINER` /
  `PUT64_CONTAINER`, derived from the base entries so every option, group and refusal is shared) and the harness
  (`equivalence_cics._translate_command` -> the same GGCPUTC / GGCGETC calls as the base command) read them that way, and
  `tests/cobol_mainframe/test_equivalence_cics.py` pins each form (CHAR / BIT, APPEND, PREPEND, NODATA, BYTEOFFSET, the CCSID
  options, RESP / RESP2) to the base command's calls and refusals. **REFUSED by name:** GET64 CONTAINER SET (it returns a 64-bit
  pointer reference; the pointer lane, X47 / X58, holds 31-bit-style blocks only), and every option the base command refuses
  (code-page names, CHAR BYTEOFFSET, ...). Neither runtime changes (the port and the stub see the base calls), so there is no
  separate cics-crucible case. No burned estate (CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication, async credit-card)
  uses either command; the scan's resource walker (`cics_resources._CONTAINER_VERBS`) does not read the 64-bit verbs yet.
- **Names (#4950).** PUT CONTAINER (CHANNEL) documents the set: "A-Z a-z 0-9 $ @ # / % ? ! : | " = , ; > . - and _.
  Leading and embedded blank characters are not permitted", with CHANNELERR RESP2 1 for an illegal CHANNEL name and
  CONTAINERERR RESP2 18 for an illegal CONTAINER name. Both runtimes model exactly that (before, any name with no blank
  was accepted, `^` or `~` included). The other commands' pages give no set and no condition.
- **Reached.** cics-crucible ca-channel-containers (2 scenarios: CHAR / BIT / APPEND, LINK and XCTL CHANNEL, the
  current channel, truncation and LENGERR, NODATA, CONTAINERERR / CHANNELERR / INVREQ by RESP and by HANDLE
  CONDITION, AEZJ by default), cobol-stub and the det port both passing the hand-written logs (crucible branch
  `cases/channel-containers`, not yet released or pinned).
- **Reached, code-page conversion (#4270).** cics-crucible `ca-container-ccsid` (hand-traced, v0.8.0; two program-source fixes in
  cics-crucible#36): `bit-container` (INVREQ RESP2 34, CCSIDERR RESP2 3 with the data returned, the same bytes without
  INTOCCSID) passes on cobol-stub and java-ported; `convert` matches IBM's log up to its event 10 (INVREQ RESP2 2, FROMCCSID 037
  read back as 1208 / 037 / the region's) and then both sides differ identically at event 11: its container `TWO` is 1208 data
  built from a hex literal, which the port and GnuCOBOL's ASCII storage keep as the characters 'ABC123' (a TS write encodes them
  as X'C1C2C3F1F2F3', not the X'414243313233' the program meant). That is the hex-literal / TS-page convention of #4528, shared by
  both sides, not a container defect.

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
  provable: its CEEDAYS passes a 10-byte picture over an 8-byte 'YYYYMMDD' (a non-blank picture tail, refused, L1). **#4952:** the case is
  `tests/equivalence/cbsa-crecust` (Db2 seed, five RUN children). The scenario `born-before-1601` (the date-of-birth
  check ends before its CEEDAYS call) runs the children and the six FETCH ANYs and, run alone through det_port, has
  all 18 events equal on both runtimes; that is not a proof of the program (13/37 paragraphs), and the committed case
  is refused by name on `create-customer` / `born-in-the-future` while L1 stands. Holes of the program: L1 (the
  CEEDAYS picture and date strings overrun their 8 bytes by 2) and this entry's ASSUMED schedule (L4 is settled: `FC` is
  the 12-byte token). BNK1CCS, which LINKs CRECUST, is not proven while they stand.
- **#4950: case-file channel names.** The harness (`scenario_channel`) refuses a channel or container name outside IBM's PUT CONTAINER set (A-Z a-z 0-9 $ @ # / % ? ! : | " = , ; > . - _; 1-16 characters, no blank) before either runtime sees it; `&`, `<` and the not sign, which RUN TRANSID's page allows and PUT CONTAINER's does not, are refused too (the pages disagree), as `ggcics.c` and the forge's `NAME_CHARS` do.
- **#4950: the cics-crucible runner does not model the child schedule.** `tests/tools/cics_crucible.py` still schedules a RUN TRANSID child as SPEC section 4 says (a request attached at once, run as a task of its own once its parent has ended), not at the parent's next wait as this entry assumes. Neither side of that runner is given `child_programs` (`childprogs.cfg` for the stub, `CicsTask.Programs.program` for the Java side), so a parent that waits (a DELAY, or a FETCH without NOSUSPEND) with a RUN child is refused by name on both sides ("its program is not one the case runs") and never compared. A parent that never waits runs its children after it ends, which is the same on both runtimes. Wiring the in-process schedule in needs a SPEC change first (a CHILD event is not in section 6.2's log, and the expected logs are IBM-recorded in the language-crucible repo), so it stays open until a case needs it (frontier; verified 2026-10-19 against cics-crucible v0.9.0: the pin test passes, all cases clear of `case_async_refusals`); no crucible case does today (`test_no_pinned_crucible_case_needs_the_child_schedule` walks the pinned crucible's cases and fails the day one is refused by `case_async_refusals`; with `test_x18_child_scope_4950.py` it is the trigger for the SPEC change). No burned program needs it either, and none needs R1 (a RUN child's ENQ / DEQ / counter / SQL): the only burned RUN children are asynccc's seven services and CBSA's CRDTAGY1-5 (a DELAY each), and the only burned parents are ASYNCPNT, CSSTATS2 and CRECUST; `tests/cobol_mainframe/test_x18_child_scope_4950.py` fails if that changes. Pinned by `tests/cics_crucible/test_cics_crucible_runner.py` (`async_refusals`): a case whose source has START or RUN with CHANNEL, a FETCH (waiting, or NOSUSPEND), FREE CHILD, or a RUN beside a DELAY or FETCH is refused by name on every run side (`unsupported`, never compared), as the disabled-program case is; a parent that never waits and RUNs a child is not.

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
- **No burned-estate proof yet (checked 2026-10-15, #5126).** No program of the six burned estates issues ASSIGN
  USERID / SCRNHT / SCRNWD (a word search of the pinned corpora finds only data names and the origin fact ODUSERID),
  so no equivalence case states `"userid"` / `"screen"` and the Docker proof is the unit and crucible-runtime tests
  only. A case that does read one states it; a non-burned program that does is out of scope.
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
- **A task whose terminal nobody states (#5126).** The stub refuses TERMCHK / FACILITY when `$GGCICS_FACILITY` is unset
  ("not stated for this task"); the port now agrees: `CicsTask` without a `withTermid` call refuses
  (`IllegalStateException`) instead of answering INVREQ RESP2 5. A stated "no terminal" (`withTermid(null)`, the stub's
  empty `$GGCICS_FACILITY`) is INVREQ RESP2 5 on both, as IBM documents. The equivalence harness states a terminal only
  for a non-empty `"termid"` (`withTermidIfStated`). `ASSIGN FACILITY` on a stated none cannot write a data area (the
  translator guards it by `TERMCHK`'s outcome), so `assignFacility` refuses rather than print "null".

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
  full-key READ answers NOTFND 80 too, #5092 / X52). READ UPDATE holds the
  record found (its own key). The stub: `GGCREAD` with GG-FLAGS `GTEQ` / `GENERIC` (`read_search`); the det port:
  `CicsTask.readSearch` over `DetCics.Store.search`.
- **ASSUMED.** RIDFLD is left as the program set it: IBM documents RIDFLD being set to the record's key for READNEXT /
  READPREV, not for READ (GenApp LGICVS01 MOVEs the found key itself). Key order is the browse's (D1: the stub's byte
  order, the det port's cp037 order); keys mixing letters and digits in one position would order differently.
- **Refused by name.** GTEQ with EQUAL and GENERIC without KEYLENGTH (the spec's option rules; both sides); a GENERIC
  KEYLENGTH of zero (IBM documents INVREQ 25 for one not shorter than the key and 42 for one below zero, both raised on
  both runtimes, X52; zero is undocumented): the translator when it is a known constant, the stub at run time ("READ
  GENERIC KEYLENGTH ..."); a KEYLENGTH the translator cannot read as
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
  IBM: "delete a group of records with a single invocation"; ASSUMED: no record is locked by another task, so none is left behind (IBM's LOCKED / RECORDBUSY outcomes, a single-task run never meets them)), NOTFND RESP2 80 when none.
  The stub: `GGCDELT` with GG-FLAGS `GENERIC`; the det port: `CicsTask.delete` over repeated `DetCics.Store.search` /
  `remove`. Refused: a GENERIC KEYLENGTH of zero (IBM is silent), a KEYLENGTH that is no constant, NUMREC (no corpus program asks for the count).
  DELETE's INVREQ RESP2 (#5092): IBM (cics-ts 6.x, `summary-delete`, Conditions) 21, "DELETE is issued for a file that refers to a
  VSAM ESDS"; 22, "A generic delete is issued for a file that is not a VSAM KSDS"; 25, KEYLENGTH with GENERIC "greater than or equal
  to the length of a full key"; 42, KEYLENGTH with GENERIC "less than zero"; 26, KEYLENGTH without GENERIC not equal to the data set's
  key length; 31, no RIDFLD and no READ UPDATE hold (X52). Modelled on both sides: `GGCDELT`; `CicsTask.delete` / `deleteGeneric` /
  `deleteHeld` / `deleteToken` answer an ESDS, `CicsTask.deleteInvalid` 25 / 26 / 42, which the translator picks for a constant
  KEYLENGTH on a known file (`Cics.delete_generic`, `Cics.file_update`) and the run time for a file named then. Order: a planned
  fault, an ESDS (21; 22 with GENERIC), then 26 / 25 / 42; nothing is deleted or released. The harness names a given non-GENERIC
  KEYLENGTH to the stub in GG-FLAGS (`KEYLENGTH`); before, a partial-key DELETE KEYLENGTH deleted by prefix on the stub. Assumed
  never to arise: INVREQ 20 (delete "not allowed by the resource definition": `files.cfg` has no such attribute), 27 (BDAM), 44, 51,
  55-57, 59 (options and file kinds the region refuses or does not have). Test: `tests/cics_crucible/test_delete_invreq_5092.py`.
  Pinned by `test_read_gteq_on_a_file_named_at_run_time_takes_that_files_key`,
  `test_delete_generic_deletes_every_record_with_the_generic_key`, `test_a_delete_generic_is_named_to_the_stub` and the
  runtime tests (`test_the_stub_delete_generic_*`, `test_cics_task_delete_generic_*`). No case runs zECS's file yet: the
  estate must state which table's file (ZCnnFILE) a case runs, the open half of #4771.
  **Template-named file (#4771 slice 2).** `FILE(ZF-FCT)` is a group, so the engine's VALUE map (elementary items only)
  left the operand unresolved and the store never got its user. `galaxy_ir._group_template` now reads a group of plain
  `PIC X` items that all carry a non-figurative VALUE as one name (`ZC##` + `FILE` -> `ZC##FILE`); the file lineage and
  the VSAM store join it to the CSD's `ZC@ID@FILE` by shape (every `#` run and `@SYMBOL@` one wildcard) when exactly one
  definition fits, and to none otherwise (a group with a run-time item, REDEFINES or OCCURS is never read). The stub then
  carries the store under `ZC@ID@FILE` and the det port emits `fileKey(name)`, which maps the run-time `ZC01FILE` onto that
  store (`cics_filecontrol.file_key_method`; a program with no template store keeps its text). ASSUMED: one shared H2 table
  stands behind every `ZCnn` instance, as the generated project has one entity for `ZC@ID@FILE`, so the instance the case
  runs cannot change the data. **Slice 3.** `ZC@ID@KEY` (ZECS003's plain DELETE by RIDFLD on the key store) has a void `deleteX(key)` stub with no
  `Optional<>` / `List<>` entity; `Generated._map_files` now names the entity from the `<entity>Repository` field, so the
  store binds. Equivalence case zecs-zecs003 states the instance (`install_symbols` ID 01, ECS_HLQ ZECS, ENVIRONMENT TEST)
  and seeds ZECS.ZC01FILE.TEST / ZECS.ZC01KEY.TEST: expired record (DELETE GENERIC KEYLENGTH 8 + key delete), fresh
  record kept, expired record with no key record; `det_port.py run` PROVED. No evidence.json: `--record` needs a committed
  port. **ZECS000 (#5089):** its names are a blank X(04) (`ZF-TRANID`, MOVEd from the RETRIEVEd transaction id) plus `FILE` / `KEY `. `galaxy_ir._runtime_names` reads such a group (an X item with no VALUE or VALUE SPACES is a run-time part) against the CSD names, `#` runs and `@SYMBOL@` standing for install-chosen characters: only a name whose fixed characters agree at every position, with at least three fixed characters and exactly one fit, binds (`????FILE` ~ `ZC@ID@FILE`); several fits or too few fixed characters name no file. Equivalence case zecs-zecs000 states the instance in `install_symbols` (ID 01) and starts the task with start data `ZC01` + a key, so ZC01FILE / ZC01KEY are the stated datasets: resume-empty-file (READ GTEQ NOTFND -> 8000-RESTART) and resume-fresh-record (kept) PROVED in both legs; since #5983 the stub serves the resolved ZC01FILE name and the expired-record path (3000-DEPLICATE: peer 201 REWRITE + SYNCPOINT, peer 404 per-segment DELETE, single segment) is in the case too. 8 scenarios, 30/38 paragraphs, 35/46 branches; `det_port.py run zecs-zecs000 zecs-zecs003` PROVED (173/173 and 73/73 translated, 2026-10-22). Pinned by `tests/cobol_mainframe/test_zecs_template_cases_5089.py`. Test: `tests/cobol_mainframe/test_template_file_lineage_4771.py`.
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
- **What IBM documents** (CICS TS 6.x, EXEC CICS LINK, ibm.com/docs/en/cics-ts/6.x?topic=summary-link: "COMMAREA(data-area) specifies a communication area that is to be made
  available to the invoked program ... LENGTH(data-value) specifies the length (halfword binary value) in bytes of the
  COMMAREA"; the invoked program's EIBCALEN is that length). A caller may pass fewer bytes than the invoked program's
  DFHCOMMAREA declares, and GenApp's services test for it: `IF EIBCALEN IS LESS THAN WS-REQUIRED-CA-LEN` -> '98', and
  WRITE-ERROR-MESSAGE's `IF EIBCALEN < 91`. What a program sees past EIBCALEN is the caller's storage after the area
  (a local LINK passes its address) or nothing CICS defines -- either way not the program's to read. IBM is silent on what a program reads past EIBCALEN, so the harness refuses it.
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
- **What IBM documents** (CICS TS 6.x, "Scope of a channel"; EXEC CICS RUN TRANSID, ibm.com/docs/en/cics-ts/6.x?topic=summary-run;
  FETCH, `...summary-fetch`; LINK, `...summary-link`; wording paraphrased. RUN TRANSID CHANNEL: "the name of the channel that is
  to be passed to the child task"; FETCH CHILD CHANNEL: "the channel returned by the child task"; LINK CHANNEL: the
  called program's current channel, "what it puts there, the caller sees"). A service started by RUN TRANSID CHANNEL,
  or LINKed with CHANNEL, finds its input in containers on its current channel and leaves its result there for the
  parent to FETCH, or for the caller.
- **IBM is silent** on a container's data type when a program reads it back across a channel, so the data type is not
  compared (below).
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
- **DEEDIT of an empty field (#6271).** An unmodified field (X'00') or an FSET field left empty (blanks) has no digit, so BNK1CAC
  437 (`CUSTNOL < 1`) and 717 (`OVERDRL < 1`) after their DEEDIT are refused by name ("no digit left"); IBM's page says nothing
  of it (re-read 2026-10-27), so no scenario types one. BNK1CAC 611/637 run only through a reference modification past
  `INTRTI` (X8, `rate-three-places` in `bounds_refused`).

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
  RETURN CHANNEL with IMMEDIATE is refused (X17: IBM does not say). IBM does not say how an immediate task orders
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
  Verified on main (#4770): ZECS001's `GET DCOUNTER(ZECS-COUNTER) VALUE(ZECS-VALUE) INCREMENT(ZECS-INCREMENT) WRAP NOHANDLE` (VALUE and
  INCREMENT are `PIC 9(16) COMP`) translates in both the det port and the stub (tests/cobol_mainframe/test_dcounter_zecs_4770.py); the
  VALUE is stored unsigned, and MINIMUM / MAXIMUM / COMPAREMIN-style options not documented for GET are refused by name. A value past the
  receiver's PICTURE is the general binary-store rule (#4684), not this command's. Superseded in part by X45 / X50 / X53 (below).
- **Not modelled / unobserved**: RESP2 of a command that completed is 0 (IBM states none: the case logs RESP2 only for a failed
  command); the order of 403 and 404 when both a pool and a counter name are invalid (the case never provokes both; the runtimes
  check the pool first); the value area of a failed GET / QUERY (not written).
- **Superseded in part by X45** (#4770): DEFINE / QUERY / DELETE DCOUNTER, MINIMUM / MAXIMUM on the doubleword form and WRAP at a
  counter's limits are modelled there; the limits (1) of GET DCOUNTER above hold only for a counter with no limits entry.
- **Superseded in part by X50** (#5039): DEFINE / QUERY COUNTER MINIMUM / MAXIMUM, GET COUNTER INCREMENT and WRAP at a fullword
  counter's limits are modelled there; the limits (1) of GET COUNTER above hold only for a counter with no limits entry.
- **LENGERR: a fullword command over a counter past 31 bits** (#4770; https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-get-counter-get-dcounter,
  ...summary-query-counter-query-dcounter). "LENGERR occurs for COUNTER commands only and does not apply to DCOUNTER requests": a counter a
  DCOUNTER command made can hold more than "a fullword signed binary value (... more than 31 bits)"; "the named counter server completes
  the operation, and returns a warning"; "the data area contains the low-order 32 bits ... which could be a negative number"; RESP2 1 "the
  value ... has overflowed into the high-order (sign) bit", 2 "too large for a fullword data area by only 1 bit ... the overflow value is
  exactly 1", 3 "by a value greater than 1"; QUERY: "LENGERR can't occur at counter-at-limit" (the value is the maximum plus one in 32
  bits: a fullword counter at X'7FFFFFFF' + 1 reads the largest negative number). Modelled (`CicsTask.fullwordGet` after a COUNTER GET,
  `CicsTask.queryCounter`, the stub's `GGCGCNT` / `GGCGCNX` / `GGCQCNT`; both translators write VALUE on RESP 22): RESP LENGERR (22), RESP2 1
  for a value of 2**31 to 2**32 - 1 (nothing above the low word), 2 when the high word is 1, 3 above; VALUE the low-order 32 bits as a
  signed number; a counter at its limit (past its DEFINE MAXIMUM) is NORMAL. GET DCOUNTER / QUERY DCOUNTER never give it. Before this the
  fullword QUERY refused the value and the fullword GET handed it out whole with RESP NORMAL. **ASSUMED**: (1) the page does not say how a value is numbered that is both a sign overflow and one bit too large (a high word of 1 with bit 31 set): the high word decides, so it is 2;
  (2) a GET that gives LENGERR has advanced the counter
  (the page says the server completes the operation); (3) a QUERY COUNTER MINIMUM / MAXIMUM of a DCOUNTER-made counter whose limits do not
  fit a fullword is REFUSED (the page does not say how a limit beyond 31 bits is returned). The same name defined by both forms is one counter
  (DEFINE of the other form: INVREQ RESP2 202; either form's GET reads it), pinned by tests/cics_crucible/test_counter_shared_namespace_4770.py.
  The register entry's `X45` / `X50` sentence "a COUNTER and a DCOUNTER of one name are one counter" is this entry's (5).
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
  it "the session token is no longer valid". Modelled (`CicsTask.webClose`, the stub's `GGCWCLS`). The connection and its end are
  recorded too (events WEB-OPEN: the host as the connection names it ('' when HOSTLENGTH gave none, the peer's for a URIMAP), the
  scheme (none when neither HTTP nor HTTPS), RESP / RESP2; WEB-CLOSE: RESP / RESP2), and the equivalence harness compares them
  (#4767). A refused open records nothing.
- **What IBM leaves open, and what we do.** (1) The server: STATED, never guessed (the case's or scenario's `http_peers`,
  `CicsTask.withHttpPeers` / `$GGCICS_HTTP`); a connection to a server, or a request, the run does not state is refused. (2) The
  token's value: ours, `GGWS` and a 4-digit sequence per task (ASSUMED: IBM only says 8 bytes). IBM sets no count of sessions a task may open or of responses a peer
  may give (#6072: ZECS000 opens 501 and never closes), so neither is capped; only the 4 digits are, and the 10000th open is refused
  by name on the stub and on `CicsTask` alike (as is a 33rd stated peer on the stub). (3) Code-page conversion: the
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
  and compares the requests (test_equivalence_cics.py). cics-crucible: its SPEC after v0.9.0 has the WEB-OPEN / WEB-CONVERSE / WEB-CLOSE
  events and an origin peer's `host`, and `gt-web-client` (crucible main, #44) runs on the runner (#6188: `tests/tools/cics_crucible.py` stages each
  origin peer from the scenario's expected conversation and maps the three events on both sides): both cobol-stub cells pass
  (a ledger row since the v0.10.0 pin, #6230: 48 `gt-web-*` cells re-run 2026-10-23, none differs from the baseline), the java-ported and java-facade cells pass with the committed det
  port of GTWCLI (#6457); the bare `java` cell is the generated skeleton and fails. zECS: with #4768's INQUIRE URIMAP direct form, ECS001 translates whole.

### X36. WEB PARSE URL (CICS web support, a URL taken apart) — ASSUMED, REFUSED where IBM is silent (#4767, zECS)
- **WEB PARSE URL** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-web-parse-url). URL "the complete URL string",
  URLLENGTH its length; SCHEMENAME "always returned in uppercase" (a 16-character area); HOST "host name or IP address",
  HOSTLENGTH the buffer size on input and "set to the returned length"; PORTNUMBER "the explicit port, otherwise the default for
  the scheme" (80 HTTP, 443 HTTPS); PATH, PATHLENGTH; QUERYSTRING "returned in escaped form", QUERYSTRLEN; escape sequences are
  checked ("%" followed by two hexadecimal characters 0-9, A-F); "not checked: that the host exists or that characters are
  permitted in a URL". Conditions modelled: INVREQ RESP2 28 "Incorrect URL", INVREQ RESP2 65 "Bad escape sequence". Listed and
  LENGERR RESP2 8 / 29 / 30 (query / host / path longer than its length): modelled as the condition alone (#4767, the crucible's
  `lengerr`): IBM says the data is truncated but not what the area or the length option then holds, so both are left alone
  (ASSUMED; a program that reads them after a LENGERR is not proven by this model, the case never does). Modelled (`CicsTask.webParse`, the stub's `GGCWPRS`; the det and
  stub translators read the option rules from the spec): the URL's first URLLENGTH bytes are parsed.
- **What IBM leaves open, and what we do.** (1) What makes a URL "incorrect": ASSUMED INVREQ 28 for no "scheme://" or an empty
  scheme, an empty host, and a port that is not 1 to 5 digits or above 65535 (IBM lists no condition for a bad port). (2) The
  pieces: the path keeps its leading "/", the query loses its "?" (ASSUMED: IBM's WEB CONVERSE takes PATH and QUERYSTRING the
  same way); the host is returned as written, without case folding (ASSUMED); an IPv6 host is written `[address]` or `[address]:port` and
  returned without its brackets (IBM, NOTES of gt-web-parse-url). (3) Areas are written on NORMAL only and only the
  piece's bytes (the rest of the area is left alone), SCHEMENAME blank-padded to its area (ASSUMED). (4) A PATH or QUERYSTRING
  asked for when the URL has none (zECS gives "http://host:port"): REFUSED, IBM does not say what the area and its length hold.
  (5) REFUSED: a scheme other than HTTP / HTTPS (IBM says only those two are "supported for use with WEB OPEN" but not whether
  the parse rejects the rest), a user-info part ("@"), a fragment ("#"), an IPv6 host that is not `[hex:colons]` / `[hex:colons]:port`, HOSTTYPE, an empty port
  ("host:"), port 0, a lowercase hex digit in an escape (IBM lists 0-9, A-F), a URLLENGTH not above zero (no condition is
  listed), a URLLENGTH or HOSTLENGTH / PATHLENGTH / QUERYSTRLEN past its area (as X6: GnuCOBOL lays out the storage that follows
  unlike IBM's compiler), two conditions at once (IBM does not order them, as X35: an INVREQ with a LENGERR, or two pieces too long). (6) The URL is parsed in the program's
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
- **cics-crucible `gt-http-inbound` (v0.9.0), checked 2026-10-17 (#4767): not servable without an owner ruling.** Its program
  GTHECHO codes `SRVCONVERT CHARACTERSET('iso-8859-1') HOSTCODEPAGE('037')` on WEB RECEIVE and WEB SEND and `MEDIATYPE('text/plain')`
  as a literal. Three things stand in the way, none of them a missing WEB command (no burned estate program needs one): (1) the
  code-page refusals above are IBM-silent on the table, and a real conversion changes the bytes the program holds, so accepting them
  as no-ops would loosen a proof; (2) MEDIATYPE is a data area in IBM's COBOL form and both translators refuse a literal there
  (`equivalence_cics._web_send`, `DetCics` via `read_field`); (3) the runner has no HTTP driver (scenario `requests`: a SERVER URIMAP
  match, trigger `{kind: http}`; the stub and `CicsTask` both record WEB-SEND and WEB-RECEIVE: the request's media type, the bytes
  returned (none on LENGERR 16), RESP and RESP2, #4767). The crucible's `gt-web-*` cases (after v0.9.0) also need the WEB-OPEN / CONVERSE / CLOSE events and peer
  host / query / headers. ZECS001 still waits on #4771.
- **The runner's HTTP driver (#4767 `[c:8672e721]`, slice 1).** `tests/tools/cics_crucible.py` now reads a scenario's `requests` and the
  case's `peers`: each request matches exactly one enabled `USAGE(SERVER)` URIMAP (IBM: SCHEME, HOST or `*`, PATH equal or a trailing-`*`
  prefix) and starts that URIMAP's TRANSACTION as an `http` task at its time (trigger `{kind: http, request: i}`, no terminal, no
  STARTCODE stated). The stub gets the request through `$GGCICS_WEBREQ` (`equivalence_cics.http_request_cfg`), `CicsTask` through
  `withHttpRequest`; both sides' WEB-RECEIVE / WEB-SEND are mapped to SPEC 6.2 events, and the task's one response is compared with the
  next response the client peer states (status, media type, body; a second or missing response, an unstated peer or a request matching no
  or two URIMAPs is the `http-peer` defined failure). A side that cannot run `http` tasks is refused by name (`scheduler: http-triggered
  tasks`). **Event order:** an ACTION(EVENTUAL) WEB SEND is recorded by both runtimes after RETURN (the response goes with the task's end);
  SPEC's expected logs put it where the command is issued, so the runner moves it ahead of the RETURN it trails (`http_order`).
  Proven on synthetic requests in `tests/cics_crucible/test_cics_http_driver_4767.py`. **`gt-http-inbound` is still refused** on the
  CHARACTERSET / HOSTCODEPAGE ruling above (the stub cell stays `unsupported`); the `java` cells now run the request and fail on the
  generated skeleton's missing events, not on "the side ran none". Left: that ruling. (The pin is v0.10.0, #6230; `gt-web-*` are ledger rows, see below.)
- **Response headers and the server `gt-web-server-*` cases (#4767 `[c:0cbe6ac6]`, checked 2026-10-23 against crucible main `ead5bf4`, past the
  v0.9.0 pin).** Both runtimes record a `WEB WRITE HTTPHEADER` as `WEB-HEADER`; the runner maps it to SPEC's `WEB-WRITE-HTTPHEADER` (name, value,
  RESP; nothing is recorded for a refused or failed write) and `http_peer_log` compares the headers the task wrote with the response's stated
  `headers` as a multiset of (name, value) pairs (order is not compared, a header written twice is two headers, a response that states none
  expects none). `WEB EXTRACT` and `WEB READ HTTPHEADER` are no events: they show in the response body the case echoes. **Both server cases stay
  `unsupported`** (stub cells; nothing moved in the ledger): `GTWRECV` / `GTWSEND` WEB SEND with `SRVCONVERT CHARACTERSET('iso-8859-1')` (and
  WEB RECEIVE's), the ruling above; and, once that is lifted, two translator refusals the cases hit: `HTTPHEADER('literal')` / `VALUE` as a
  literal ("a data area is the COBOL form", both translators) and `VALUELENGTH(3)` (a literal) on WEB READ HTTPHEADER, which the translators
  `MOVE` back into. The mapping is proven on synthetic stub lines and peer responses (`test_cics_http_driver_4767.py`), not yet on a case.
- **Pinned `gt-web-*` ledger rows (#4767 `[c:0cbe6ac6]`, checked 2026-10-23 at the v0.10.0 pin, #6230).** The four cases are served and counted: engine-facts and
  forge-compile pass on all four; cobol-stub passes on `gt-web-client` (2 of 2) and `gt-web-parse-url` (1 of 3: `errors` passes, `parse` and `lengerr` fail at
  a missing WRITEQ-TS); `gt-web-server-receive` (4) and `gt-web-server-send` (1) stay `unsupported` on CHARACTERSET / HOSTCODEPAGE (refused, X37); every java /
  java-ported / java-facade cell fails on the generated skeleton (no port). `cics_crucible.py --ci` on these cases: 48 cells, 0 differ from
  `tests/cics_crucible/baseline.json`, so no re-baseline.

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
  (a new object), a failed XCTL, level 1 and the XCTL target's own DTO are not refused. A String or number cannot be traced by
  reference (#5060), so a successful XCTL whose COMMAREA equals a value the DTO holds (any field, nested or primitive) is refused
  too; an equal-valued copy is over-refused (refuse, never guess), a value the DTO does not hold is not. Numbers match by numeric value whatever their width or scale (an int field passed as a long, 1.5 and 1.50), and an element of a primitive table (`int[]`, `char[]`) is a value the DTO holds.
- **Reach on the burned estates (#5060).** No burned program is both LINKed and an XCTL issuer: CardDemo's XCTL programs are
  started by transaction, `ZECS001` XCTLs but LINKs out to `ZECS002`, which does not XCTL, and CardDemo's one LINK
  (`COPAUS1C`) targets a program that is not in the corpus. The value forms are therefore refused by equality tracing and
  unreached. A value derived from a field (a suffixed String, a sum) cannot be traced and passes as a new value (pinned in
  `test_model_link_xctl_4956.py`).
  Re-checked 2026-10-19 against the six burned corpora: XCTL issuers are CardDemo's 21 online programs and `ZECS001` only;
  the LINK targets are CBSA, GenApp, the async credit-card example, DBB `EPSMLIST` and ZECS002 (none issues an XCTL), plus
  CardDemo's one data-driven `WS-PGM-AUTH-FRAUD`. No program is both, so the model-port value forms are unreached there.
- **Aliases (#4957).** The det port marks an XCTL whose COMMAREA lies inside any LINKAGE 01 record, not only DFHCOMMAREA: a CALLed
  subprogram's USING record (`CALL 'SUB' USING DFHCOMMAREA`) is the LINK caller's storage under another name, and refuses by the
  same runtime check (only when the program was LINKed with a COMMAREA). `SET ADDRESS OF` (direct or through a pointer) is
  translated since #4771 (X47) and its record is a LINKAGE 01 record like any other, so it carries the same mark and refuses
  by the same runtime check; the oracle's `ggcics.c` compares addresses, so it refuses every alias form.
- **Calibration kit (#5060).** `tests/tools/xctl_commarea_capture_kit.py emit OUTDIR` writes three CICS COBOL programs (a driver
  that LINKs, a middle program that XCTLs its whole DFHCOMMAREA, a group inside it and a `SET ADDRESS OF` alias, and a target that
  writes `TGT` and RETURNs); `verdict SYSOUT` reads the run's `X39-<case>|<area>` lines and says `same-storage`, `copy`, `mixed` or
  `invalid` per case. It is the real-CICS run this item waits on: it changes no model, and the refusal is replaced only by a person
  who reads a captured run (record the CICS release and the output's sha256 here). The kit's COBOL has not been compiled on z/OS.
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
  REDEFINES overlays other than by a pure numeric view (a PIC X or group view; ZECS001's CACHE-ADDRESS-X is a pure view, see Pointer arithmetic below), and any statement but the two address idioms that names an item that
  REDEFINES a POINTER, or one under it (ADD, SUBTRACT, MOVE, COMPUTE, IF on the numeric view; a MOVE / INITIALIZE of the whole group holding
  both still copies the handle bytes), since it would compute on handle bytes; SET ADDRESS OF / ADDRESS OF a record that is not a
  LINKAGE 01 (a WORKING-STORAGE record shares its section's storage; a subordinate item such as ZECS001's ZF-DATA has no storage of its own);
  SET ADDRESS OF ... TO NULL. At run time: a length above 256 MiB (IBM's NOSTG is the region's DSALIMIT, not stated) or a LENGTH above 65520; a
  second FREEMAIN of a block (IBM does not say); FREEMAIN of a WEB RECEIVE SET body (IBM does not say whether it is allowed); SET ADDRESS OF a
  null or unknown pointer, or freed storage; a record longer than storage that another record already addresses.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Unit-proven only (see `reached`): both runtimes answer 24 step lists alike, the
  translator's shape and every refusal are tested in tests/cobol_mainframe/test_det_translate.py and test_equivalence_cics.py, and a whole program
  with the four statements translates with no hole and runs (tests/cobol_mainframe/test_pointer_lane_4771.py). No cics-crucible case or estate
  program exercises it yet, so no port moves and no ZECS program is made whole by this entry.
- **CALL ZUIDSTCK (#4771, #5945): a stand-in whose 16 bytes the run states, ASSUMED: see X69.** ZECS001's 4000-GET-COUNTER keeps only `THE-TOD(1:6)` as a record
  key prefix; the 16 bytes are opaque and stated on both runtimes, executed-equivalent on zecs-zecs001 (2 stated TODs). The entry, its IBM context and the
  no-reader check are X69.

- **Pointer arithmetic (#4771, ZECS001): the two address idioms, ASSUMED.** ZECS001 advances CACHE-ADDRESS by the bytes it copied (`ADD ZF-LENGTH TO
  CACHE-ADDRESS-X`), copies the address (`MOVE CACHE-ADDRESS-X TO SAVE-ADDRESS-X`) and sets CACHE-MESSAGE to the advanced address. *The 4- versus
  8-byte decision:* a POINTER stays 8 bytes in the port (the oracle's width, GnuCOBOL x86-64; IBM's is 4), and its `PIC S9(8) COMP` view is **never
  read as a number**. A pure view (an elementary BINARY integer item that REDEFINES a POINTER and has nothing under it,
  `program.pointer_view_of`) is modelled for exactly two statements: `ADD|SUBTRACT n TO|FROM view` (one operand, one target, no ROUNDED, no ON SIZE
  ERROR) is `DetCics.advancePointer`, which gives the pointer the handle of the same block n bytes on (`CicsTask.addressOf(bytes, offset)`, the windowed
  `Storage` of slice 1), and `MOVE view TO view` is `DetCics.copyPointer`. Anything else that names a view (COMPUTE, IF, MOVE to or from a number or
  a group view, ADD GIVING, several operands) is still refused by name ("a REDEFINES overlays a POINTER with it"), as is a pointer overlaid by anything
  but pure views (a PIC X view, a group). At run time a result outside the block (below its first byte or past its last), a null or a freed pointer is
  refused by name. **Not proven against the oracle:** GnuCOBOL's `ADD n TO view` is a big-endian read of the low half of a little-endian 8-byte address,
  so its result is no address the program can use; this is unit-proven on the port only (test_pointer_lane_4771.py), and nothing
  here is "executed-equivalent". A SET ADDRESS OF a record longer than the block's rest after an advance is the existing refusal ("a record longer
  than its storage"): ZECS001's 32000-byte CACHE-MESSAGE over a short tail refuses at run time, so the estate program's behaviour past a short segment is
  not modelled (assumption 2 above).
  2026-10-22 (#5945): ZECS001 translates 560 of 561 statements with the forge's `runTask` stub; the one hole is the missing COMMAREA DTO the stub does
  not carry (line 753), not a pointer hole (the corpus test pins it); CALL ZUIDSTCK (line 1244) is the stand-in above (it was a named hole, 559 of 561). Evidence level for the pointer lane on ZECS001: translated (560 of 561, pointer holes 0), unit-run on the port (windowed
  `Storage`, `advancePointer` / `copyPointer`), not executed-equivalent against the oracle (GnuCOBOL's 8-byte view differs, see above).
  2026-10-22 (#5945, estate survey): `cics_census.py survey` over the whole zecs estate (generated DTOs, not the stub) takes ZECS001 561 of 561, 0 holes;
  with its case (zecs-zecs001, two stated TODs, equal) the evidence report puts it at L2 (paragraph coverage 31.1%, the next bar).
  2026-10-22 (#5945, oracle item closed): the oracle side is `le/zuidstck.c` (#5979); a parity test now pins that every `cobolrt/le` stand-in has a
  `tests/equivalence/le` twin. Evidence: executed-equivalent, zecs-zecs001, 2 stated TODs, 0 diffs; the 16 bytes stay opaque (ASSUMED).
  Still refused in the pointer lane: the siblings listed on #5042.

- **GETMAIN without INITIMG: the burned-estate census (#4270, 2026-10-17).** Over the burned corpora (baseline `cf0bcb927a5e`: 98 of 106 CICS
  programs translate whole) one program issues it, DBB MortgageApplication `epscsmrd.cbl` (ALLOCATE-DFH-BODY-WORK-AREA and
  ALLOCATE-DFH-DATA-WORK-AREA: `GETMAIN SET FLENGTH`, then `SET ADDRESS OF` the block). It stays REFUSED, and lifting it would move nothing: the
  program also issues `SOAPFAULT CREATE` (web services, out of scope of #4270, X65) and calls `EPSCSMRI` / `EPSCSMRO` / `EPSCSMRX`, which the
  estate holds no source for, so it can neither translate whole nor be given a case. IBM leaves the contents undefined, so a lift would need the
  run to STATE a fill byte on both runtimes (`CicsTask.withGetmainFill`, `$GGCICS_GETMAIN_FILL`, refused when unstated) and a burned program that
  reads the block before writing it. Reopen when a burned program has this as its only gap. No other burned program issues a GETMAIN, LOAD or
  RELEASE; every other CICS verb a burned program uses has a full spec entry.

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
  not cut. A RETURN whose LENGTH is past the DTO passes the COMMAREA as a `byte[]` in the region's EBCDIC (#4679): the task's
  `returned(Object.class)` is that `byte[]`, `returned(Dto.class)` refuses it by name, and `returnedBytes()` is null (the bytes
  are the answer itself). A det facade's `handleTransaction` (both overloads) answers the program's own DTO read from them
  (the service's `wideAnswer`: the DTO's `fromCommarea` layout, #4449, after undoing the region's EBCDIC), so a deployed caller never
  sees opaque bytes; EIBCALEN and the bytes stay the task's for the next one, and `lastAnswerBytes()` is unchanged. A DTO with
  no layout, or bytes shorter than its record, are answered as before: an `Object` facade keeps the `byte[]`, a typed one is
  refused by name (`returned(Dto.class)`); a facade with no DTO of its own (`Object
  request`) keeps the `byte[]`; a forge-generated (model-written) facade is unchanged (#4695).
- **A LENGTH that differs from the record (#5089).** IBM hands the next task exactly LENGTH bytes (EIBCALEN = LENGTH), so a
  record longer than LENGTH was never passed past it, and bytes of a LENGTH longer than the record are storage that follows the
  item, laid out unlike IBM's by GnuCOBOL: undefined. A DTO with no `fromCommarea` layout (a POINTER refuses one; the generator
  writes layouts only into DTOs a facade converts between) is read from the passed bytes through the program's own storage codec
  (`codecAnswer`): the bytes past the record are dropped, a trailing POINTER the LENGTH stops short of reads NULL (the only
  pointer a COMMAREA carries, `DetCics.pointerOut`), and fewer bytes than the non-POINTER properties need are answered null, i.e.
  refused by name as before, never guessed. The harness (`answered`) checks the read by writing the DTO back through the codec
  (`wideSame`) and comparing the bytes over the span both sides define: a differing byte inside it still fails. CBSA BNK1UAC
  (LENGTH 99 of 107 bytes, trailing POINTER), BNK1TFN (LENGTH 29 over 28) and BNK1CCS (LENGTH 248 over 5) are answered; ASSUMED
  like the cut above. Not covered: a POINTER before another field (the codec's offsets shift; C9) or under an OCCURS (refused).
- **DTO-only answer (#4817).** A DTO holds a number it decoded, so a DTO-only answer of a RETURN (`returned(..)` of a task whose
  `returnedBytes()` was not read: the one-arg `handleTransaction`, the REST endpoint over it) is refused by name when the DTO's
  layout bytes (`toCommarea`) differ from a byte the RETURN passed, unless the DTO's byte is a space (FILLER, an unset field;
  0x20 or 0x40, the page being unknown to CicsTask). The byte-carrying `handleTransaction(.., byte[])` reads `returnedBytes()` first
  and answers as before. A DTO with no layout, or a RETURN with no bytes beside it, is unchanged. The check is a lower bound: a loss under a space byte of the DTO's layout is not seen.
- **Round trip (#5053).** A kept `byte[]` answer is the region's EBCDIC, while the bytes beside a request (the byte-carrying
  `handleTransaction` / `handleLink` `area`, `lastAnswerBytes()`, `lastLinkBytes()`) are in the port's page. An `Object` request
  that is itself a `byte[]` together with an `area` is one COMMAREA in two charsets: that facade overload stops by name
  (`IllegalArgumentException`) rather than take either. A typed request cannot be a `byte[]`; no committed port changes
  (`det_port.py check`: 122/122 unchanged).
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
- **The full-key READ's NOTFND / INVREQ RESP2 (#5092 box 4).** IBM (cics-ts 6.x, `summary-read`, Conditions): NOTFND RESP2 80, "an attempt
  to retrieve a record based on the search argument provided is unsuccessful"; INVREQ RESP2 26, KEYLENGTH specified without GENERIC and not
  the file's key length; 25, GENERIC with KEYLENGTH "greater than or equal to the length of a full key"; 42, KEYLENGTH "less than zero".
  Modelled on both sides (`ggcics.c` GGCREAD, `CicsTask.read` / `readSearch` / `readInvalid`, the translator's `Cics._keylength` for a
  constant KEYLENGTH on a known file), for plain, UPDATE, TOKEN, GTEQ and GENERIC reads; a NOTFND or INVREQ holds nothing and issues no
  token; INVREQ 28 is answered before a KEYLENGTH check, a planned fault before both. Spec: `standards/cics/commands/files.py` READ Outcomes.
  The harness (`equivalence_cics.py`) names a given non-GENERIC KEYLENGTH to the stub in GG-FLAGS (`KEYLENGTH`), as the stub cannot tell it
  from LENGTH OF RIDFLD. Test: `tests/cics_crucible/test_read_resp2_5092.py`.
- **Assumed (#5092).** INVREQ RESP2 20 (READ or READ UPDATE "not allowed by the resource definition"): `files.cfg` carries no such
  attribute, so every file allows both and 20 never arises. A KEYLENGTH of any value without GENERIC and with RIDFLD longer or shorter than
  it is INVREQ 26 whenever it differs from the key's length (IBM states 26 for "not equal").
- **Refused by name (#5092).** A GENERIC KEYLENGTH of zero (IBM is silent). The values bound to options or files the region refuses: INVREQ
  40 (BDAM), 44, 51-53, 55, 59 and NOTFND 81 (RBA / XRBA, CONSISTENT, REPEATABLE, NOSUSPEND), 56 and 57 (coupling-facility data tables,
  RREPL): those options are refused at translation and the file kinds do not exist in the region.

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
  Re-read 2026-10-23 (#5116, c:9d9ee016, every citation in this page against the live DFHMDF page): each sentence quoted above
  (JUSTIFY, LEFT, RIGHT, BLANK, ZERO, both "If JUSTIFY is omitted" sentences, GRPNAME, "OCCURS and GRPNAME are mutually exclusive",
  PICIN, PICOUT) matches word for word. The page's assumption table for a half-coded JUSTIFY reads LEFT assumes BLANK, RIGHT assumes
  ZERO, BLANK assumes LEFT, ZERO assumes RIGHT. It also says JUSTIFY "is ignored for VTAM-supported 3600, 3650, and 3790 terminals,
  because input mapping is not available" (not modelled: no burned map targets one), and that without PICIN/PICOUT "a character
  definition of the field is automatically generated regardless of other operands that are coded, such as ATTRB=NUM". The page
  states nothing about JUSTIFY on an OCCURS or GRPNAME field (per-occurrence JUSTIFY stays frontier, below).
  (Re-read 2026-10-19 (#5116, closing the NUM-default item): the two "If JUSTIFY is omitted" sentences still match the live page word for word.
  Re-read 2026-10-18 (#5116): every JUSTIFY sentence quoted above, and the two "If JUSTIFY is omitted" sentences, matches the
  live page's text word for word.)
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
  data stream, so a field erased with ERASE EOF (the cics-crucible's convention: `<f>L` 0, flag `<f>F` X'80' = DFHBMEOF) is not modelled
  by the equivalence harness or the det port (#4506). An unmodified field is: `<f>L` 0, data and flag X'00' on both legs. (#4506, MDT) A field with FSET in its DFHMDF has its MDT on, so a terminal transmits it even when left alone: `<f>L` 0 and blank data (ASSUMED: IBM does not
  say what the data area holds); a field without FSET is not transmitted and stays X'00'. The generated input follows both: an `empty` share on a field
  rule (or on `@bms`) sends an FSET field empty and omits any other. Reached: COTRN01C `TRNIDINI = SPACES OR LOW-VALUES` (FSET, carddemo-tranview-generated)
  and BNK1DAC `ACCNOI = LOW-VALUES OR ACCNOL = 0` (not FSET, cbsa-bnk1dac-generated, `empty` 0.2 on ACCNOI). No burned program reads DFHBMEOF, so ERASE EOF stays unmodelled.
- **NUM default (#5116).** A field with no JUSTIFY but ATTRB=NUM is right-justified and zero-filled, as IBM assumes. The forge's
  `_justify` returns the effective operand (`RIGHT,ZERO` for it), so `ScreenField.justify`, `Cics.receive_map`'s `DetJustify.place`
  and the oracle's `bms_justify` / `map_input` all take the one rule, and the cics-crucible runner (`cics_bms.received_value`)
  reads the same: an explicit JUSTIFY is as coded (LEFT / BLANK where a half is left out), so `JUSTIFY=(BLANK)` on a NUM field is
  left-justified. A NUM field's generated screen class now carries `"RIGHT,ZERO"` in LAYOUT; a port that RECEIVEs one moves.
- **JUSTIFY on SEND MAP: not applicable.** IBM: JUSTIFY "specifies the field justifications for input operations", so the output
  map keeps the program's text as is (SEND MAP is not modelled to justify, and need not be).
  Re-read 2026-10-22 (#5116, c:5781930a): the live DFHMDF page says JUSTIFY "specifies the field justifications for input operations." and
  nothing in it gives JUSTIFY an output effect. Pinned by `test_det_send_map_never_justifies_5116` and
  `test_the_oracle_output_side_never_justifies_5116` (`Cics.send_map` and `compare_events` never read it).
- **PICIN / PICOUT: out of scope, by name.** They are pictures given to the *generated symbolic-map field* (compile-time: the item's
  PICTURE in the copybook) and BMS does not check or convert the data at run time ("the validity of the input data is not checked by
  BMS"); no run-time conversion exists to model. The symbolic map's PICTURE is already what the layouts read.
  Re-read 2026-10-23 (#5116, PICIN/PICOUT box) against the live DFHMDF page (https://www.ibm.com/docs/en/cics-ts/6.x?topic=macros-dfhmdf):
  PICIN "specifies a picture to be applied to an input field in an IN or INOUT map; this picture serves as an editing specification
  that is passed to the application program, thus permitting the user to use the editing capabilities of COBOL or PL/I." "BMS checks
  that the specified characters are valid picture specifications for the language of the map." "However, the validity of the input data
  is not checked by BMS or the high-level language when the map is used, so any wanted checking must be performed by the application
  program." PICOUT "is like PICIN, except that a picture to be applied to an output field in the OUT or INOUT map is generated." The
  page states no run-time conversion or validation of data against either picture. Pinned by `test_x54_records_picin_picout_no_runtime_conversion_5116`
  and `test_det_receive_and_send_map_never_read_a_picture_5116` (`Cics.receive_map` / `Cics.send_map` never read `picin` / `picout`). The burned
  maps that declare pictures (CardDemo COACTVW, CBSA BNK1DAM / BNK1UAM) have them in the generated symbolic-map field PICTURE, the one place both the
  oracle and the det layouts read them: `test_burned_map_pictures_become_the_symbolic_field_picture_5116`.
- **Not modelled, by name.** (1) A GRPNAME group's later fields take the first field's ATTRB (so NUM, hence the NUM default); the
  forge reads each field's own ATTRB, so a group member without one is treated as non-NUM. (2) OCCURS: the DFHMDF page says nothing of
  JUSTIFY per occurrence (an OCCURS field is one operand set, so each entry would take the field's one JUSTIFY: ASSUMED, not
  IBM text; re-read 2026-10-24, #5116, c:63fe8de1: no sentence joins JUSTIFY with OCCURS, GRPNAME, "each occurrence" or "group"),
  and a screen's OCCURS field is not received at all by `Cics.receive_map` (its values are keyed `NAME.n`,
  which `screen_fields` does not list) and the oracle refuses a symbolic map with OCCURS by name ("BMS OCCURS"); OCCURS and GRPNAME
  are mutually exclusive in IBM, so the two never combine.
  Census (#5116, `test_bms_occurs_grpname_census_5116.py`): of the burned estates' BMS maps no field uses GRPNAME, and the
  only OCCURS is CBSA `BNK1ACC` `ACCOUNT` (`OCCURS=10`, `ATTRB=(NORM,PROT,FSET,ASKIP)`, output only), so no burned program
  RECEIVEs into one: per-occurrence JUSTIFY and GRPNAME ATTRB inheritance stay unmodelled, frontier only. The test fails
  when a burned map gains either. Per-occurrence JUSTIFY is therefore closed for the burned estates: no program can reach it,
  and a burned map that gains a typable OCCURS or any GRPNAME field fails the census before a wrong proof can pass.
  The harness side is the same: `Unsupported("BMS OCCURS input")` (`equivalence_cics.py`, RECEIVE MAP typing into `NAME(n)`) stays by
  design, since no burned map has a typable OCCURS field and `bms_input_fields` never offers one (pinned by
  `test_no_burned_occurs_field_is_generated_as_map_input`, #4506).
- **Not modelled: input over initialized data (#5116).** The DFHMDF page adds: "If a field is initialized by an output map or
  contains data from any other source, data that is typed as input overwrites only the equivalent length of the existing data;
  surplus existing data remains in the field and could cause unexpected interpretation of the new data.". The harness gives the program the typed text placed per JUSTIFY, never merged over
  an earlier value. Reachable: typable (not ASKIP/PROT) fields with an INITIAL exist in 15 burned maps (CBSA BNK1B2M/CAM/CDM/
  MAI/TFM, CardDemo COACTUP/COPAU00/CORPT00/COSGN00/COTRN00-02/COUSR00, mortgage epsmort, GenApp ssmap), pinned by
  `test_burned_maps_with_a_typable_initial_field`. Whether a 3270 buffer or the program's map area is what the note means is
  unsaid; settling it needs the same z/OS calibration as `<f>L`. No model change until then.
- **Open (#5116): what `<f>L` holds after justification.** IBM is silent (assumption 3); settling it needs real z/OS
  calibration, not a doc reading. Blocked on that calibration; the model keeps the typed length until a z/OS run says otherwise.
  Only one burned program depends on it, cbsa-bnk1cac (it reads `<f>I(1:<f>L)` of NUM fields), and it sidesteps the question by
  typing its rates at the field's full width. A calibration run must record the `<f>L` value after a short input into a
  `JUSTIFY=(RIGHT,ZERO)` field (and a NUM field with no JUSTIFY). Until then no model change is made: a guess would loosen a proof.
- **Generated map input (#4506).** The harness types into a map from its BMS source: a `scenario_generate` receive entry `"MAP": "@bms"`
  (`tests/tools/equivalence_inputs.py` `bms_input_fields` / `_bms_receive`) gives every typable DFHMDF field a value. Typable: named, not
  ASKIP or PROT, not OCCURS; a field with no ATTRB is ASKIP (the forge's `_attrs`; `cics_bms.attr_byte` agrees), and an OCCURS field is left
  untyped because `map_input` refuses it by name. A NUM field and a PICIN of 9s get digits, the rest letters and digits, at the BMS LENGTH (the
  narrower of LENGTH and the PICIN width); `bad` types text that is not a number into a NUM field (CICS does not check it; a real 3270 keyboard
  would refuse it) and `empty` leaves a field alone (no data, `<f>L` 0).
- **MDT and the null convention (#4506).** `bms_input_fields` reports `mdt` for a field with ATTRB FSET (the map sends it with its
  modified-data tag on, so a 3270 transmits it whether or not the user typed). A field left alone with MDT off is not transmitted: RECEIVE MAP
  leaves it X'00' with `<f>L` 0 and `<f>F` X'00' (oracle `map_input` and the det port's zeroed INTO area agree). A field left alone with
  MDT on is generated as transmitted with no data (`""`: `<f>L` 0, blank data on both legs). ASSUMED: IBM is not quoted here for what an
  MDT-on field that was never touched returns (the sent content, here none), and the IBM RECEIVE MAP page was not re-read for this slice.
  Census: no burned program reads `<f>F` or DFHBMEOF (they only move DFHBMFSE into `<f>A`); burned programs do test emptiness
  (`= SPACES OR LOW-VALUES`, e.g. COTRN01C on `TRNIDINI`, FSET, case carddemo-tranview-generated), which both an omitted and an
  empty-transmitted field satisfy. Not modelled: ERASE EOF (assumption 4) and X'00' rather than blank data for a transmitted empty field
  (differs only for a program testing `= LOW-VALUES` alone).
- **Output map compare (#4506).** `equivalence_cics.compare_events` pairs SEND MAP events in order and compares: `map`, `mapset`, every
  `<f>O` data field (error-message fields included), per field the attribute byte (`<f>A`), extended colour (`<f>C`) and highlight
  (`<f>H`), the cursor (`<f>L` = -1 and `CURSOR(n)`) and the options; an event on one side only is a diff. Pinned one element at a time in
  `tests/cobol_mainframe/test_output_map_compare.py`. Not claimed: a subfield of X'00' (LOW-VALUES, "the map's own") or X'40' (DFHBMUNP, which
  the port's side cannot tell from a cleared byte; COPAUS0C hits it), and bytes a program never set (GnuCOBOL spaces where IBM leaves them
  undefined). Sibling, not folded in: #5116 (PICIN/PICOUT, SEND MAP JUSTIFY, NUM default); no burned program was found to need it.
- **A field of typed blanks arrives with length 0 (#6271, assumption 5).** The oracle (`map_input`, `justified`) and the port
  (`DetCics.typed`, `DetJustify.place`) take `<f>L` as the length of the text typed without its trailing blanks, so a blank
  amount is `AMTL` 0. IBM's DFHMDF / RECEIVE MAP pages do not say whether blanks typed count in `<f>L` (re-read 2026-10-27), and a
  real 3270 may send them. Consequence: BNK1CRA 988 and BNK1TFN 1026 ("entirely spaces", `AMTL` above 0) are not reached; the
  `AMTL = ZERO` guard (BNK1CRA 970, BNK1TFN 991) takes every blank amount. Both outcomes are stated in
  `tests/equivalence/infeasible_outcomes/cbsa-bnk1cra.json` / `cbsa-bnk1tfn.json` as unreachable under this assumption, not as
  impossible on a terminal. A length independent of the text would need a new input channel (oracle, DetCics, DetJustify,
  translator): not modelled.

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
- **A cell or pointer tested for no address (#5197).** IBM's relation condition (Enterprise COBOL for z/OS Language Reference, "Conditional
  expressions", pointer comparisons; the manual's section was named, its page not checked) compares a pointer only for = and NOT =, with
  NULL or another pointer, never with a number. An OS/VS COBOL cell is a fullword, so `IF cell = ZERO` is its test for no address, and
  IBM's conversion makes the cell a POINTER: `bll.py` reads `cell [NOT] = ZERO|ZEROS|ZEROES|NULL|NULLS|LOW-VALUE|LOW-VALUES` (#5042; IS / EQUAL [TO] spellings, either
  operand order) as `cell [NOT] = NULL`; the port tests the pointer's handle for zero (X47: NULL is all-zero bytes, `Cobol.compareFigurative`
  against LOW-VALUES) and GnuCOBOL runs its own `= NULL`. Refused by name: a pointer against ZERO or any non-pointer (IBM: invalid), `>` `<`
  `>=` `<=` on a pointer, NULL against NULL, a table / REDEFINES-overlaid / subscripted pointer, a long record's secondary cell (it is no
  pointer after the lowering), `cell > ZERO` and every other cell comparison ("used as a number"), NULL as an operand of MOVE or arithmetic.
  Tests: tests/cobol_mainframe/test_pointer_null_cond_5197.py.
- **A pointer or cell against another pointer or cell (#5042).** IBM allows `=` and `NOT =` between two pointers. Two pointers are equal
  when they address the same storage; the det port's handle equality is `CicsTask.samePointer` (the same handle, or two handles whose
  blocks hold the same bytes: `ADDRESS OF rec` after `SET ADDRESS OF rec TO p` is a second handle for p's block, since a record's
  handle is per byte array), and GnuCOBOL's own pointer = pointer is native. `bll.py` reads `cell [NOT] = cell` the same way. The
  abbreviated `p = q OR r` and `p = q OR NULL` take the same two tests. Refused by name: `>` `<` `>=` `<=` between pointers, `ADDRESS OF`
  as an operand of a relation (IBM defines the special register's value as a pointer, but the det port holds a record's handle only once
  it is addressed, so `ADDRESS OF rec = NULL` has no defined handle: ASSUMED refusal). Tests:
  tests/cobol_mainframe/test_pointer_compare_5042.py (the unit cases and one program proven against GnuCOBOL).
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

### X59. ADDRESS EIB / COMMAREA modelled; ADDRESS CWA / TWA / TCTUA / ACEE, SEND PAGE and PURGE MESSAGE refused by name (#5079; CONVERSE, POST, WAIT EVENT: X63)
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
  - **CONVERSE** (terminal), **POST** and **WAIT EVENT** were refused here by #5185; they are modelled by X63 (#5079), which carries their IBM pages.
    WAIT EXTERNAL and WAITCICS stay name-only (X63).
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
  ENQ. (4) INVREQ 2 / LENGERR 1 are not planned: the translated program raises them from its own operands. IBM: LENGTH "must be in the range 1 through 255; otherwise, the LENGERR condition occurs" (LENGERR RESP2 1),
  and MAXLIFETIME CVDA values are UOW (default), LUW ("a compatibility alias for UOW", the same CVDA 246) and TASK (233); INVREQ RESP2 2
  is "the MAXLIFETIME option is set with an incorrect CVDA". So LENGTH outside 1-255
  gives LENGERR RESP2 1 and a MAXLIFETIME CVDA that is neither DFHVALUE(UOW) / (LUW) (246) nor DFHVALUE(TASK) (233) gives INVREQ RESP2 2,
  on both runtimes (`CicsTask.enqChecked`, the stub's `GGCENQ`: GG-LEN / GG-NUM, GG-NAME2 'L' / 'M' say which were written); the
  failed ENQ records the event with its RESP2 and takes no resource. (5) LENGTH and MAXLIFETIME both bad at once: IBM names no
  order, so both runtimes REFUSE. A bad operand is checked before a plan's ENQBUSY (ASSUMED: IBM states no order).
- **Refused by name:** the list in the summary.
- **Status:** ASSUMED for RESP2 0, REFUSED where listed. Unit-proven on both runtimes, LENGTH / MAXLIFETIME included (tests/cics_crucible/test_enq_fault_5089.py).

### X61. Transient-data queues past X57: READQ TD SET / NOSUSPEND, extrapartition input queues, RECOVSTATUS(LOGICAL), INDIRECT, seeded queues, SET / INQUIRE TDQUEUE OPENSTATUS — ASSUMED, REFUSED where IBM is silent (#5168)
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
- **SET / INQUIRE TDQUEUE** (round 3; https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-set-tdqueue, https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-tdqueue).
  SET OPENSTATUS (extrapartition queues only): "whether the data set associated with the queue is to be open or closed", CVDAs OPEN ("the data
  set is to be opened") and CLOSED. INVREQ RESP2 8 "OPENSTATUS has an invalid CVDA value", RESP2 9 "OPENSTATUS was specified for an
  intrapartition queue", RESP2 16 "the JCL DDNAME to which the queue definition points was not found"; QIDERR RESP2 1 "the queue cannot be
  found". ENABLESTATUS (for an extrapartition queue only availability changes, the data set is not opened or closed), ATIFACILITY and
  TRIGGERLEVEL (intrapartition only) are other options of the same command. INQUIRE OPENSTATUS (extrapartition queues only): CLOSED, CLOSING,
  OPEN, OPENING, or NOTAPPLIC "the queue is not extrapartition"; TYPE: EXTRA, INDIRECT, INTRA, REMOTE; QIDERR RESP2 1; the page lists no INVREQ.
  CVDAs (det/cvda.py): OPEN 18, CLOSED 19, NOTAPPLIC 1, EXTRA 221, INTRA 222, INDIRECT 122, REMOTE 4. The run-time state (the stub's
  `td-<hex>.open` beside the queue's directory, `CicsTask.TempStorage.tdOpen`) is the queue's state for READQ TD, WRITEQ TD and INQUIRE from then on,
  across tasks; before any SET it is what OPENTIME says. INQUIRE of an INDIRECT queue answers about that queue (TYPE INDIRECT, OPENSTATUS NOTAPPLIC),
  not its target.
- **Assumed, round 3.** (8) SET to the state a queue is already in is NORMAL (IBM is silent). (9) RESP2 16 does not arise: the DDNAME is taken as found.
  (10) The CLOSING and OPENING states are never reached: one task, and a SET completes before the next command. (11) INQUIRE OPENSTATUS of an
  INDIRECT or REMOTE queue is NOTAPPLIC (it "is not extrapartition"); a REMOTE queue's definition is answered locally. (12) A closed output queue
  reopened writes on (the run keeps no output data). (13) SET OPEN is allowed on an INPUT queue no record has been read from; a queue closed
  and reopened with TYPEFILE(OUTPUT) is as before.
- **What the runtimes do.** The stub reads each definition's attributes from `tdqueues.cfg` (`NAME TYPE KEY=VALUE ...`; the harness writes only the
  ones the CSD states, `csd_tdqueue_attrs`), CicsTask from `withTdQueueAttributes`. READQ TD SET is the INTO form's read (same conditions, same
  event) followed by a block of the record (`GGCRDTS`; `DetCics.setBlock` with the key `READQ TD`, so the next READQ TD ends it). An open
  extrapartition input queue reads the records a case seeds (the case's or scenario's `"td": {"QUEUE": [record, ...]}`, ASCII text; the stub's
  `ts/td-<hex>/NNNNNN.bin`, `CicsTask.TempStorage.seedTd`) exactly as an intrapartition queue does. A LOGICAL queue's first read, write or delete
  since the last SYNCPOINT saves it (the stub's `td-<hex>.uow`); SYNCPOINT drops the copy, SYNCPOINT ROLLBACK restores it. An INDIRECT queue is
  followed to its target before the CSD lookup, the QIDERR test, the records and the recoverability; the READQ-TD / WRITEQ-TD event keeps the
  queue name the program gave.
- **Assumed.** (1) NOSUSPEND has no effect unless a scenario plans QBUSY (round 9): one task at a time touches a queue, so QBUSY never arises of itself. (2) RECOVSTATUS not stated, or NO, is
  committed at once (IBM states no default; this is X57's assumption (2)). (3) A task reads its own uncommitted writes to a LOGICAL queue (IBM
  speaks of other tasks only). (4) OPENTIME not stated is INITIAL. (5) A task's abend (one no HANDLE ABEND exit takes) backs a LOGICAL queue out to its state at the last SYNCPOINT, in the
  stub and in CicsTask alike (IBM: "restored to the state at the end of the last completed unit of work"; a PHYSICAL queue touched since
  is refused); an abend taken by an exit backs nothing out. CicsTask refuses only a SYNCPOINT ROLLBACK after a SYNCPOINT (files).
  (5b) WRITEQ TD to an extrapartition queue with no TYPEFILE (or RDBACK) is taken as open for output, as before; only TYPEFILE(INPUT)
  and OPENTIME(DEFERRED) change the answer. (6) A queue defined TRIGGERLEVEL(n) with a TRANSID counts the records it holds
  (seeded ones included) plus the one being written. (7) The data set behind an input queue holds exactly the case's records and has no
  read error.
- **Refused by name** (stub and port stop at the statement, "not modelled"). SYSID (a remote system) and a queue of TYPE REMOTE; IOERR as a condition of the data (no data set to fail; round 8 plans it, below); an extrapartition queue with no TYPEFILE or with RDBACK; SYNCPOINT ROLLBACK after a read, write or delete of a RECOVSTATUS(PHYSICAL)
  queue (what IBM backs out of a READQ is not specified further); a WRITEQ TD that brings a queue with a TRANSID to its TRIGGERLEVEL (automatic
  task initiation starts a task the run does not model); an INDIRECT queue with no INDIRECTNAME, whose target the CSD does not define, or in a
  chain that loops; READQ TD INTO with SET; SET without a LENGTH data area (IBM's SET page for the TS form says LENGTH "must be specified"; the TD
  page states no more than the record's length goes there), or with a literal LENGTH. IOERR on a write is a planned fault only (the harness's WRITEQ-TD plan, as before); a write to an open output queue records the event and
  writes nothing.
- **Refused by name, round 3** ("not modelled"; ENABLESTATUS has since moved to X66, #5168 round 5; INQUIRE TRIGGERLEVEL, RECOVSTATUS and TRANSID in round 6). SET TDQUEUE with any option but OPENSTATUS (ENABLESTATUS, ATIFACILITY, ATITERMID, TRIGGERLEVEL ...) and
  INQUIRE TDQUEUE with any option but OPENSTATUS / TYPE (the browse START / NEXT / END included); SET OPENSTATUS of an INDIRECT or REMOTE queue (IBM names
  only the intrapartition case); an invalid CVDA on a queue that is not extrapartition (IBM does not order RESP2 8, RESP2 9 and QIDERR); OPENSTATUS(OPEN)
  of an extrapartition queue with no TYPEFILE INPUT / OUTPUT; OPENSTATUS(OPEN) of an input queue a READQ TD has read from (reopening restarts the data
  set, whose records the run has consumed); INQUIRE of a queue with no TYPE stated.
- **Round 4: the messaging forge's TD runtime** (`RoutingTransientData`, #3620; the same IBM pages as above). A generated port has no RESP, so a
  condition is thrown (`TdCondition`, `.condition` NOTOPEN / INVREQ) and a refusal is an `UnsupportedOperationException` ending ": not modelled".
  From the CSD (`csd_resources` facts) it takes TYPEFILE, OPENTIME and INDIRECTNAME, and answers as the stub and CicsTask do: an INDIRECT queue is
  its INDIRECTNAME's (chains followed); an extrapartition queue that is closed (OPENTIME DEFERRED) is NOTOPEN for READQ and WRITEQ; TYPEFILE(INPUT)
  is read first in first out from `<gitgalaxy.td.directory>/<target>.txt` (nothing left, or no such file: empty, QZERO. ASSUMED: IBM's missing
  DDNAME is INVREQ RESP2 16 on SET only) and WRITEQ is INVREQ; TYPEFILE(OUTPUT) READQ is INVREQ; DELETEQ TD of an extrapartition queue is INVREQ
  (checked before NOTOPEN, as X57 states it for the type). Unchanged: a queue the CSD does not define stays intrapartition (the port has no QIDERR);
  a log destination is written, not read; a WRITEQ to an extrapartition queue with no TYPEFILE is taken as open for output (ASSUMED). Refused by
  name: SYSID and TYPE REMOTE queues, an INDIRECT queue with no INDIRECTNAME / an undefined target / a loop (more than 8 hops), READQ of an
  extrapartition queue with no TYPEFILE INPUT / OUTPUT (RDBACK included). Not modelled in the forge (no counterpart in a port): RECOVSTATUS rollback,
  seeds, SET / INQUIRE TDQUEUE, READQ SET. Proven by compiling and running the generated class (tests/cobol_mainframe/test_td_forge_5168.py); no
  equivalence oracle backs it, so it is a model alignment, not an executed-equivalent proof.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. The oracle is GnuCOBOL plus the stub, not z/OS.
- **Round 8: IOERR on READQ TD** (a planned fault, `READQ-TD` in a scenario's `faults`, `TD_READ_FAULTS` in `tests/tools/equivalence_cics.py`;
  same IBM READQ TD page). IBM: IOERR "an input/output error"; "the data record in error is skipped"; no RESP2 is listed. ASSUMED: the
  skipped record is consumed (the next READQ TD reads the one after it), nothing reaches INTO / SET and LENGTH is unchanged; the plan is
  consulted only by a read that reaches the data set (an open extrapartition queue, a LENGTH not below zero, not DISABLED), so NOTOPEN, INVREQ,
  LENGERR, QIDERR and DISABLED answer first and do not count toward `nth`; an INDIRECT queue counts under the name the program gave; a plan
  on an intrapartition queue is never consulted. Only IOERR with no RESP2 may be planned (other conditions follow from the queue; QBUSY needs
  a second task). Stub and CicsTask agree on 7 scenarios in `tests/cics_crucible/test_td_queue_5168.py`. No burned-estate program reads a
  TD queue (CardDemo's CORPT00C only writes, and its WRITEQ TD IOERR is already planned in `carddemo-report`), so READQ TD IOERR has no
  corpus program to prove against.
- **Round 9: READQ TD NOSUSPEND and QBUSY** (a planned fault, `READQ-TD` in a scenario's `faults`, `TD_READ_FAULTS` in `tests/tools/equivalence_cics.py`;
  same IBM READQ TD page, #6228). IBM: QBUSY (25) "occurs when READQ targets a logically recoverable intrapartition queue that another task is
  writing to or deleting from, and no committed records remain"; NOSUSPEND: "if the queue is already in use for output, the task is not
  suspended". The page lists no RESP2, so QBUSY carries none. The translator passes NOSUSPEND to `CicsTask.readqTd` and, as the token `TDNOSUSPEND`
  in GG-FLAGS, to the stub (`FETCH` also leaves NOSUSPEND there; `GGCRDTD` reads the token and clears the field).
  ASSUMED: every record on the queue counts as committed, a record written in the same unit of work included (a second task cannot exist in this
  region); the plan is the only source of "another task"; the plan is consulted only by a NOSUSPEND read of a LOGICAL intrapartition queue
  holding no record. REFUSED by name: QBUSY planned without NOSUSPEND (IBM suspends the task), QBUSY planned on an extrapartition queue, IOERR
  planned on a LOGICAL intrapartition queue; `HANDLE CONDITION QBUSY` without NOSUSPEND is not read. Stub and CicsTask agree on 7 scenarios in
  `tests/cics_crucible/test_td_queue_5168.py`. No burned-estate program reads a TD queue with NOSUSPEND, so this is a synthetic proof against
  the stub, not an executed-equivalent one against z/OS. WRITEQ TD and DELETEQ TD QBUSY are not modelled.

### X62. CICS runtime resource state (CEDA / CEMT / CEDA INSTALL) is not read: only resource-definition sources are (#5154)
- **IBM.** CEDA defines and installs resource definitions in a running region and CEMT inquires on and sets installed
  resource state; the installed state lives in the region and its catalogs, not in a repository file.
- **What we do.** `gitgalaxy/core/cics_macro_tables.py` and the CSD reader lift definitions only. `GalaxyIR.resource_conflicts`
  already says that "CICS installs whichever is loaded last, which the source tree cannot say".
- **Refused.** Any claim that a resource is installed, enabled, or has a given runtime value. A dump of CEMT / CEDA output
  placed in a repository is not a definition source and is not read.
- **Assumed.** Still by name, because IBM has no page for them in the CICS TS 5.x library (re-tried for #5154): DFHJCT
  `JFILEID=` / `JTYPE=` (IBM says only that JFILEID is "supported for compatibility purposes only"), DFHPCT's operand
  list, DFHPPT `PARTITIONSET=` / `PARTSET=`, and DCT SDSCI `RECFORM=UNDEFINED`. The CICS/VS and
  CICS/ESA 3.x macro manuals are the references to confirm against.
- **Confirmed (no longer assumed).** DFHSIT `SUFFIX=`: one or two characters, not NO or DY, SIT only (TS 5.4
  dfha2_suffix); the SIT row is named DFHSIT + suffix.
- **Refused, with the IBM reason.** SIT parameters (table suffixes, GRPLIST=) as rows: they select what a start-up
  loads, and `SIT=` / SYSIN can override them. DFHMCT `TYPE=RECORD` (selects performance fields, no named resource).
  DFHTCT `TYPE=GPENTRY` (no IBM page in the TS 5.x library, so nothing is read). DFHTCT `TYPE=SDSCI` / `TYPE=LINE` (a DD of a simulated sequential device, and the join of two of them; the terminal
  is the `TYPE=TERMINAL` row).
- **Joined.** An assembler step (or a DFHAUPLE call) whose `SYSIN DD` is `DSN=lib(MEMBER)`: `GalaxyIR.job_macro_tables`
  names the member's macro-table rows beside the job step, one entry per DD (an unnamed DD concatenated after the SYSIN
  is its own entry; DFHAUPLE's override is `//PROCSTEP.SYSIN`, reported under the EXEC step). Each entry carries a
  `status`: `joined`, `no_tables` (the member file is found and has no macro-table row), `not_found`, or `ambiguous`
  (two files of that name; no guess). **Refused by name:** any other wrapper proc, a qualified `//STEP.PROCSTEP.SYSIN`
  DD, and a DSN with no member.

### X63. POST, WAIT EVENT and terminal CONVERSE modelled; WAIT EXTERNAL / WAITCICS, CONVERSE on a conversation and SEND PAGE / PURGE MESSAGE refused by name (#5079)
- **POST** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-post). "This 4-byte control area is initialized to binary zeros" and
  is posted when the time expires or another transaction cancels the POST: "its first byte is set to X'40' and its third byte to X'80'". SET
  returns "the address of the 4-byte timer-event control area generated by CICS"; REQID is 1-8 characters and, omitted, CICS generates one and
  returns it in EIBREQID. The time is INTERVAL(hhmmss) (default INTERVAL(0)), TIME(hhmmss), or AFTER / AT HOURS MINUTES SECONDS (HOURS 0-99,
  MINUTES 0-59, SECONDS 0-59, or one of them alone: MINUTES 0-5999, SECONDS 0-359999). Conditions: EXPIRED "if the specified time has already
  passed", INVREQ RESP2 4 / 5 / 6 for hours / minutes / seconds out of range. "A task can have only one active POST at a time": a later POST, a
  CANCEL of the POST, a local START or a DELAY ends the area ("The timer-event control area can be released ...": a WAIT on it is then
  "unpredictable").
- **WAIT EVENT** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-wait-event). ECADDR "specifies the address of the timer-event control area that must
  be posted before task activity can be resumed"; NAME labels the task in INQUIRE TASK (SUSPENDVALUE / HVALUE). INVREQ RESP2 2: the address is a null
  pointer (X'00000000' or X'FF000000'); RESP2 3 / 4 / 6 (above the 16 MB line, not fullword-aligned, user-key storage another transaction cannot
  read) cannot arise: a pointer here holds the handle of a block of task storage the region lays out itself.
- **What the runtimes do.** The area is a new block of task storage (the pointer lane, X47 / X58: `CicsTask.acquireSet`, the stub's `blk_set_new`), the
  pointer holds its handle, and `SET ADDRESS OF rec TO ptr` shares the bytes, so a program reads the posting through its own record. POST registers its
  REQID with the task's unexpired requests, so CANCEL REQID finds it (NORMAL while the expiry is later than the stated clock, X18); the expiry is
  `now + interval`, or the time of day (a TIME / AT of today that has passed is EXPIRED, one with hours above 23 is on the day after). WAIT EVENT on an
  area not yet posted dispatches the RUN children not yet run (X18), moves the scheduler's clock to the expiry and posts the area; EIBTIME and ASKTIME
  stay as dispatched (X4). EIBRESP / EIBRESP2 and RESP / RESP2 as for any command.
- **Assumed.** (1) A task takes no time, so a POSTed area is posted by a WAIT EVENT or a CANCEL only, never by the clock under a running task; the
  program can poll the area only with SUSPEND (IBM's suggestion), which is refused by name (a name-only entry), so no program polls. (2) A WAIT EVENT on an area already
  posted returns at once (IBM does not say). (3) A POST with no REQID runs under POST0001, POST0002 ... in EIBREQID (IBM: "CICS generates one"). (4) An
  EXPIRED POST makes no area and leaves SET's pointer as it was (IBM does not say what the pointer holds). (5) A CANCEL of the POST by the task itself posts
  the area (IBM: another transaction's CANCEL does) and releases it: nothing the program reads of it afterwards is defined by IBM, and a WAIT EVENT on it is
  refused.
- **CONVERSE (default)** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-converse-default). FROM "names the data sent to the terminal", FROMLENGTH / FROMFLENGTH its length (FROM's
  length when omitted), INTO "the receiving field for the data read from the terminal", TOLENGTH / TOFLENGTH "the length of the data to receive" (with INTO
  and without MAXLENGTH it sets the most the program accepts; a negative value is zero), MAXLENGTH / MAXFLENGTH the most to recover ("a negative value is
  treated as zero"), NOTRUNCATE keeps the rest for later RECEIVEs; LENGERR when the reply is cut ("the TOLENGTH area is set to the original data length")
  or a length is out of range. The region's terminal is the one 3270 display of X15: the send is recorded as a plain SEND records it (a SEND-TEXT event with
  the data), the receive is `receive` (the operator's input, read once per task; a second terminal read would wait for the operator and is refused, X15).
  Assumed: a negative FROMLENGTH is LENGERR with nothing sent and nothing read (IBM calls the value out of range and gives no RESP2).
- **Refused by name.** Translating: CONVERSE SET (the reply in a block: RECEIVE SET is X58; CONVERSE's pointer validity is not stated), every option of the APPC /
  distributed conversation form (CONVID, STATE, ATTACHID, STRFIELD ...), a CONVERSE without FROM or INTO, POST's options other than the ones above,
  WAIT EVENT without ECADDR, a pointer that is no plain USAGE POINTER item. Running: WAIT EVENT on an address that is no POST's area, on an area a later POST,
  CANCEL, local START or DELAY ended (IBM: unpredictable), CONVERSE on an LUTYPE2 terminal (the reply's last byte raises EOC, which IBM does not list for
  CONVERSE). WAIT EXTERNAL and WAITCICS stay name-only (an ECB of the program's own, not a POST's timer-event control area).
- **Still refused (X59):** SEND PAGE and PURGE MESSAGE, which complete and discard a BMS logical message (ACCUM / PAGING), which SEND MAP and SEND TEXT refuse.
- **Status:** ASSUMED where listed, REFUSED where IBM is silent. Reached by no corpus program yet, so no port moves. cics-crucible cases to add (separate queue
  items): POST AFTER + WAIT EVENT + CANCEL NOTFND; a POST then a second POST (the first area ended: refused); CONVERSE with a reply that fits and one that is cut
  (LENGERR, TOLENGTH the original length); WAIT EVENT on a null pointer (INVREQ RESP2 2); POST TIME already past (EXPIRED).

### X64. EIB fields no command sets: EIBDS is modelled; EIBFN, EIBRCODE, EIBCPOSN, EIBREQID, EIBRSRCE, EIBERR / EIBERRCD stay unmodelled and are named (#5126)
- **What IBM documents** (CICS TS 6.x, EIB fields, https://www.ibm.com/docs/en/cics-ts/6.x?topic=reference-eib-fields):
  - EIBDS "Contains the symbolic identifier of the last data set referred to in a file control request." COBOL
    PIC X(8).
  - EIBFN "Contains a code that identifies the last CICS command issued by the task." PIC X(2); the values are IBM's
    "Function codes of EXEC CICS commands" table.
  - EIBRCODE "Contains the CICS response code returned after the function requested by the last CICS command ...
    has been completed." PIC X(6); "For a normal response, this field contains hexadecimal zeros (6 X'00')". A
    condition's value is a row of IBM's EIBFN / EIBRCODE / condition table, with seven notes (SYSIDERR, SESSIONERR,
    SYSBUSY, INVREQ and LENGERR of terminal control, ILLOGIC / IOERR of file control carrying a BDAM or VSAM return
    code, INVMPSZ).
  - EIBRSRCE "the symbolic identifier of the resource being accessed by the latest executed command", by command type
    (a map name, a file name, a transaction, a journal, a program, a TS or TD queue, a terminal); EIBREQID the request
    identifier CICS assigned to an interval control command; EIBCPOSN the cursor address of the last terminal or BMS
    input; EIBERR / EIBERRCD an APPC conversation's error (X'FF' and its code).
- **EIBDS (modelled).** A file control command (READ, READNEXT, READPREV, RESETBR, STARTBR, ENDBR, WRITE, REWRITE,
  DELETE, UNLOCK) with a FILE or DATASET operand moves that operand into EIBDS before the request runs, on both sides
  in a program that reads EIBDS (the stub's driver, `equivalence_cics.translate`; the det port, `Cics.command`); a
  program that never reads it keeps its text. The MOVE pads or truncates to 8 characters as IBM's X(8)
  does. ASSUMED: IBM says "referred to", not "completed", so a request that fails (FILENOTFOUND, NOTFND ...) still
  names its file; a command that is refused is refused as before and sets nothing. No other command touches EIBDS.
- **Not modelled, refused by name.** EIBFN, EIBRCODE, EIBCPOSN, EIBREQID, EIBRSRCE, EIBERR and EIBERRCD are
  INITIALIZEd on both sides (spaces / zero): equal, but not z/OS's value. EIBFN and EIBRCODE need IBM's full function
  code and condition tables, row by row, for every command a program can issue; EIBRSRCE a per-command-type resource
  (a map name is 7 characters, a journal number a halfword); EIBCPOSN the 3270 cursor, which no scenario states;
  EIBREQID a CICS-assigned request id; EIBERR / EIBERRCD an APPC conversation (no APPC model). A program that reads
  one keeps its `fact: NAME` gap in `proof_blockers.py`, so no proof says anything about the value it reads. Even
  EIBRCODE's documented normal value (6 X'00') is not set, because a half-set field would turn the gap into a wrong
  claim after any non-normal response.
- **Reached.** Burned estates: ZECS001 reads EIBDS and EIBRCODE (`9100-FILE-ERROR`, `9200-KEY-ERROR`, and eight
  `MOVE EIBDS(1:8)` after a failed file request), a program the det port translates with holes and no
  case runs yet; no other burned program reads any of the seven. Pinned by
  `tests/cobol_mainframe/test_eibds_5126.py` (both translators, every file verb and spelling, the programs that do
  not read EIBDS) and `tests/tools/test_proof_blockers.py`.
- **Re-measured 2026-10-16 (#5077, origin/main cf0bcb927; `cics_census.py survey --baseline --no-census`, then
  `proof_blockers.py --json`).** 98 of 106 burned-estate CICS programs translate whole; no whole program lists a
  `fact:` gap of any kind (EIB field, ASSIGN STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD, APPLID / SYSID). The
  seven programs #5077 counted were false positives of the fact scan (EIB names inside literals and hyphenated data
  names such as CBSA's `EIBRCODE-NICE`, fixed by #5125) plus cases that did not state STARTCODE (LGIPVS01, LGICVS01,
  ASYNCPNT and SEQPNT state it). The one real EIBRCODE read, ZECS001's `MOVE EIBRCODE TO FE-RCODE`, is absent from the
  gap list because ZECS001 is not translated whole (pointer arithmetic over REDEFINES'd addresses, `CALL ZUIDSTCK`),
  so `proof_blockers` ranks it nowhere; no burned program reads EIBFN as a value (ZECS000, ZECS001 and ZECS003 name it
  only in `VALUE 'EIBFN: '` literals).
- **Why EIBFN / EIBRCODE stay unmodelled (decision, #5077).** The mainframe evidence policy (burned estates only) leaves
  nothing to prove: the only reader is a program with holes and no case, and EIBRCODE's file-control values are VSAM
  return codes inside ILLOGIC / IOERR that GnuCOBOL's file status cannot supply. A table copied from IBM with no
  program to run it would be unexecuted claim. They remain `fact: NAME` gaps in `proof_blockers.py`, so a program that
  starts reading one is listed at once; model them (EIBFN from IBM's function-code table, EIBRCODE per condition row)
  when a whole burned program reads one.
- **Guard (2026-10-19, #5126).** `tests/cobol_mainframe/test_eib_fn_rcode_5126.py` scans the six burned estates' COBOL
  with `proof_blockers.facts_needed` and pins ZECS001 (EIBRCODE) as the only reader of EIBFN, EIBRCODE, EIBCPOSN,
  EIBREQID, EIBRSRCE, EIBERR and EIBERRCD. A new reader fails it, which is the trigger above to model the field:
  IBM's tables verbatim, then the stub, `Cics.command` and `equivalence_cics.py` scenarios. The blind and census
  estates are not opened (PL/I's `UNSPEC(EIBRCODE)` in the dsf clone is a census count, not a reader here).
- **Re-checked 2026-10-20 (#5126, origin/main c913eb622).** The guard above passed against the six burned estates
  (`test_eib_fn_rcode_5126.py`, `test_eibds_5126.py`, `test_proof_blockers.py`: 101 passed, none skipped), so ZECS001
  is still the only reader. What remains of #5126 is EIBFN / EIBRCODE, blocked on IBM's verbatim function-code and
  condition tables; the other checklist boxes are done (#5144, #5186, #5221, #5261, #5346, #5664).
- **Re-checked 2026-10-22 (#5126, origin/main 14ebb0303).** The guard (`test_eib_fn_rcode_5126.py`, `test_eibds_5126.py`,
  `test_proof_blockers.py`: 101 passed) still finds ZECS001 as the only burned reader of the seven fields, so no whole
  burned program reads EIBFN or EIBRCODE and the trigger above has not fired. The decision stands: no function-code or
  condition table is copied without a program that runs it. Sibling gaps, none needed by a burned program: EIBCPOSN,
  EIBREQID, EIBRSRCE, EIBERR / EIBERRCD (named, refused). (ASSIGN FACILITY with no terminal, listed here before, was
  aligned on the stub and the det port in #5346.)
- **Re-checked 2026-10-24 (#5126).** Same result: ZECS001 is the only burned reader, it translates with holes and has no
  case, and IBM's verbatim tables are still not at hand. Do not requeue the EIBFN / EIBRCODE box until the guard fails
  or ZECS001 becomes whole.
- **Evidence level.** Translated on both sides and pinned at the translator (the text each side emits); NOT
  executed-equivalent: no case's program reads EIBDS, so no scenario ran the stub's MOVE against the port's. The
  detail the pins cannot show is the MOVE's padding on the Java side (`Cobol.move` into the X(8) field).
- **So a proof says:** a case's program that reads EIBDS sees the file it last named, on both sides. It does NOT say
  anything about EIBFN / EIBRCODE / the rest, which stay gaps.
- **Re-checked 2026-10-25 (#5126, origin/main fc4484eb9).** Same result: the guard (`test_eib_fn_rcode_5126.py`) passes,
  ZECS001 is the only burned reader of the seven fields, it translates with holes and has no case, and IBM's verbatim
  function-code and condition tables are still not at hand. The `ASSIGN FACILITY` wording above is current (#5346
  aligned the stub and the det port). Nothing was modelled: EIBFN / EIBRCODE stay `fact:` gaps by name.

### X65. The EXEC CICS commands refused whole by name, by class, with the reason for each (#4270)
- **What this entry is.** #4270's last acceptance line: "every still-refused verb listed in the register with a reason". The spec
  (`gitgalaxy/standards/cics/commands/api.py`, `_NAME_ONLY`) holds one name-only entry per refused command, with the reason and
  IBM's page (`https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-<command>`; the page names follow IBM's summary index and
  were not each opened for this entry). `Command.register` is X65 for all of them except DUMP TRANSACTION (X46), SEND PAGE and
  PURGE MESSAGE (X59), WAIT EXTERNAL and WAITCICS (X63).
- **Refused, never assumed.** None of these commands has a modelled outcome, so there is no ASSUMED part. A program that issues one
  is not translated whole and cannot be proven, and its hole names the command and the class reason.
- **Classes and reasons.**
  - BTS (ACQUIRE, ADD SUBEVENT, CHECK, DEFINE, DELETE, ENDBROWSE / GETNEXT / STARTBROWSE, INQUIRE, LINK ACQPROCESS / ACTIVITY, RESET,
    RETRIEVE REATTACH EVENT / SUBEVENT, REMOVE SUBEVENT, SIGNAL EVENT, TEST EVENT, FORCE TIMER, EXTRACT PROCESS): business transaction
    services need processes, activities, events and timers the region does not define. INQUIRE CONTAINER is documented by IBM only for a
    BTS data-container, so it is refused with the BTS reason (a channel's containers are read by STARTBROWSE CONTAINER, GET CONTAINER NODATA).
  - DTP and GDS (ALLOCATE, CONNECT PROCESS, BUILD ATTACH, EXTRACT ATTACH / ATTRIBUTES, FREE, WAIT CONVID / SIGNAL, GDS ...): APPC, LUTYPE6.1
    and MRO conversations need a partner system; the region is one system.
  - Batch data interchange (ISSUE ADD / END / ERASE / ...): a 3770 / 3790 / LUTYPE4 logical unit's data sets; the region has one 3270 display.
  - Terminal control beyond that display (ISSUE COPY / DISCONNECT / ERASEAUP / LOAD / PASS, ROUTE, SEND PARTNSET, RECEIVE PARTN, SIGNON /
    SIGNOFF, WAIT TERMINAL): routing to other terminals, partitions and logical device codes.
  - Security (VERIFY PASSWORD / PHRASE / TOKEN, CHANGE PASSWORD / PHRASE, QUERY SECURITY, REQUEST PASSTICKET / ENCRYPTPTKT, EXTRACT
    CERTIFICATE): the region has no security manager and no signed-on user to answer them.
  - Web services (INVOKE SERVICE / WEBSERVICE / APPLICATION, SOAPFAULT, WSACONTEXT, WSAEPR) and TRANSFORM: out of scope of #4270
    (separate issue); TRANSFORM needs the XML / JSON binding files.
    SOAPFAULT CREATE (the one the burned DBB epscsmrd issues) names IBM's options (CLIENT, FAULTSTRING, FAULTSTRLEN ...) in the spec
    so they read as known words; the command is still refused whole (#5235).
  - Journals (JOURNAL, WRITE JOURNALNAME / JOURNALNUM, WAIT JOURNALNAME / JOURNALNUM) and the JES spool (SPOOLOPEN / READ / WRITE / CLOSE):
    log streams and the spool are not modelled.
  - DOCUMENT INSERT / SET / DELETE: only DOCUMENT CREATE and RETRIEVE are modelled (X33).
  - OpenTelemetry (OTEL), user trace and monitoring (ENTER TRACENUM, MONITOR): no trace or monitoring facility is modelled.
  - 64-bit storage (GET64 / PUT64 CONTAINER, GETMAIN64, FREEMAIN64): the pointer lane (X47) holds 31-bit-style blocks only.
  - LOAD and RELEASE: a program or table loaded into storage and addressed by a pointer; the engine derives the load edge, the translator
    refuses both. No burned estate issues either (0 programs in the census of the burned and local corpora); LOAD is heavy only in PL/I.
  - Singles: SUSPEND and CHANGE TASK (one task runs at a time), RESETBR (browse repositioning), ADDRESS SET (X59), BIF DIGEST,
    CONVERTTIME (a date-time string to ABSTIME).
- **Status:** REFUSED. Reached by no burned-estate program except DBB MortgageApplication's SOAPFAULT CREATE; non-burned census programs are counted by tools
  only. A command here moves to its own X entry when a slice models it, and its `register` changes with it.
- **The modelled side (#4270 acceptance 3).** `tests/cobol_mainframe/test_cics_command_evidence_4270.py` pins that every modelled
  command has a register entry, a cics-crucible case in the committed status file, or a named unit-proof test that issues it
  (its `UNIT_PROOF` list, which only shrinks). A census of the burned estates (2026-10-18) finds none using a command or ASSIGN /
  INQUIRE option listed here as refused, so no new verb was modelled in that slice.

### X66. Transient-data queues: SET / INQUIRE TDQUEUE ENABLESTATUS and the DISABLED condition on READQ / WRITEQ / DELETEQ TD — ASSUMED, REFUSED where IBM is silent (#5168 round 5)
- **SET / INQUIRE TDQUEUE ENABLESTATUS** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-set-tdqueue,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-tdqueue). SET ENABLESTATUS: ENABLED makes the queue available, DISABLED makes it
  unavailable ("for an extrapartition queue only availability changes, the data set is not opened or closed"). INVREQ RESP2 10 "ENABLESTATUS has an
  invalid CVDA value"; QIDERR RESP2 1 "the queue cannot be found". INQUIRE ENABLESTATUS: ENABLED, DISABLED (and DISABLING, which one task never
  reaches). CVDAs (det/cvda.py): ENABLED 23, DISABLED 24; DFHRESP DISABLED is 84.
- **DISABLED on the queue commands** (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-readq-td and the WRITEQ TD / DELETEQ TD pages). "DISABLED:
  the queue has been disabled", listed as a condition of all three commands; no RESP2.
- **Assumed, round 5.** (1) A queue is ENABLED until a SET says otherwise (IBM's ENABLESTATUS default is the definition's; the CSD attributes the engine reads
  state none). (2) DISABLED is answered before NOTOPEN and the extrapartition INVREQs, and before QZERO (IBM does not order them). (3) The state outlives the
  task and is not rolled back by SYNCPOINT ROLLBACK or an abend (it is not a unit-of-work resource). (4) SET to the state a queue is already in is NORMAL
  (X61 assumption (8)). (5) INQUIRE of an INDIRECT queue answers about that queue (ENABLED unless set), not its target, as OPENSTATUS and TYPE do (X61).
  (6) A command on an INDIRECT queue follows the chain first and is judged by the target's state, as for every other condition. (7) The state is held
  beside the queue (the stub's `td-<hex>.enable`, `CicsTask.TempStorage.tdDisabled`).
- **Refused by name** ("not modelled"). SET TDQUEUE with OPENSTATUS and ENABLESTATUS together (IBM states no order for their errors); SET ENABLESTATUS of an
  INDIRECT or REMOTE queue (which queue it reaches is not stated); an invalid CVDA on a queue the CSD does not define (IBM does not order QIDERR and
  INVREQ RESP2 10).
- **Not modelled, no burned program needs it.** The burned estates' only TD command is WRITEQ TD (CSSL, JOBS, STDQ-NAME); none reads or deletes a TD queue or
  issues SET / INQUIRE TDQUEUE. DISABLED therefore has no consumer yet: this round is the same mechanism as X61 round 3, kept to what both runtimes can answer.

## Round 6: INQUIRE TDQUEUE TRIGGERLEVEL, RECOVSTATUS and TRANSID (#5168)

- **INQUIRE TDQUEUE TRIGGERLEVEL / RECOVSTATUS / TRANSID** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-inquire-tdqueue).
  TRIGGERLEVEL: a fullword, the number of records that starts the ATI transaction (default 1, 0 disables ATI), intrapartition only. TRANSID: the
  4-character transaction started at the trigger level, intrapartition only. RECOVSTATUS: PHYSICAL (215), LOGICAL (216), NOTRECOVABLE (30), or
  NOTAPPLIC (1) when the queue has no recovery attribute.
- **Assumed, round 6.** (1) TRIGGERLEVEL is the CSD's value, else 1. (2) TRANSID is the CSD's, else blanks. (3) RECOVSTATUS of an intrapartition queue is
  LOGICAL / PHYSICAL as defined, NOTRECOVABLE when the CSD states none; any other queue type answers NOTAPPLIC. (4) The options are read-only: nothing
  changes state, no ATI is fired. (5) The answers are about the named queue (an INDIRECT queue is not followed), as OPENSTATUS and TYPE.
- **Refused by name.** INQUIRE TDQUEUE TRIGGERLEVEL or TRANSID of a queue that is not intrapartition (IBM names no value): "INQUIRE TDQUEUE TRIGGERLEVEL /
  TRANSID of a queue that is not intrapartition: not modelled", on both runtimes. SET TDQUEUE TRIGGERLEVEL has since moved to round 7; ATIFACILITY, ATITERMID stay refused.
- **Output slots.** The stub reads TRIGGERLEVEL, RECOVSTATUS and TRANSID back in GG-HOURS, GG-MINS and GG-RTRAN (spare fields, no copybook change); the det port
  reads them from `CicsTask.inquireTdQueue`'s 6-boolean overload (`[5]`, `[6]`) and `tdTransid`.
- **Not modelled, no burned program needs it.** Same as above: the burned TD users only issue plain WRITEQ TD.

## Round 7: SET TDQUEUE TRIGGERLEVEL (#5168)

- **SET TDQUEUE(q) TRIGGERLEVEL(n)** (CICS TS 6.x, https://www.ibm.com/docs/en/cics-ts/6.x?topic=commands-set-tdqueue). TRIGGERLEVEL is a fullword: the number of
  records that starts the ATI transaction, intrapartition only, 0 disables ATI. QIDERR RESP2 1 when the queue cannot be found.
- **Assumed, round 7.** (1) The new level replaces the CSD's for every later task and is read back by INQUIRE TDQUEUE TRIGGERLEVEL and by the WRITEQ TD
  automatic-task-initiation check (X61 refusal at the trigger level). (2) It is not a unit-of-work resource: a SYNCPOINT ROLLBACK or abend keeps it
  (as ENABLESTATUS, round 5). (3) Setting 0 disables the ATI refusal; setting it back restores it. (4) The state is held beside the queue (the stub's
  `td-<hex>.trig`, `CicsTask.TempStorage.tdTrigger`).
- **Refused by name** ("not modelled"). SET TRIGGERLEVEL of a queue that is not intrapartition (IBM names no value), a level below zero (or above a 32-bit
  fullword on the Java side); SET with OPENSTATUS or ENABLESTATUS together with TRIGGERLEVEL (IBM states no order for their errors). ATIFACILITY and ATITERMID stay refused.
- **Not modelled, no burned program needs it.** No burned estate issues SET TDQUEUE; proof is synthetic (hand-traced operation lists on both runtimes, the translators' shapes
  and refusals in tests/cobol_mainframe/test_td_enablestatus_translate_5168.py).

### X67. HANDLE ABEND PROGRAM refused by name: an abend exit program is not modelled (#4270)
- **What is refused.** `HANDLE ABEND PROGRAM(name)` (IBM, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-handle-abend):
  the named program gets control when the task abends, in place of a paragraph of the issuing program. Modelling it needs the
  abend to transfer control to another program at the issuing level (as an XCTL does) with the abend code available to it,
  in both runtimes (`CicsTask` / `DetCics` and `ggcics.c`), and a hand-traced crucible case; none of that can be proven on a
  burned program, because none uses it.
- **Refused, never assumed.** The translator's hole names the option and this entry; the program is not translated whole.
  `HANDLE ABEND LABEL`, `CANCEL`, `RESET` are unchanged (X31 for the abend path).
- **Status:** REFUSED. It moves to its own modelled entry when a burned program needs it.

### X68. EIBTRNID, a stated fact of the run — the case's transaction id, not the region's CSD (#4707)
- **What IBM documents** (CICS TS 6.x, EIB fields, https://www.ibm.com/docs/en/cics-ts/6.x?topic=reference-eib-fields):
  EIBTRNID "Contains the symbolic identifier of the transaction currently being executed. COBOL: PIC X(4)." Which id a
  task runs under is set by the region (the TRANSACTION resource definition that attached it, or the START / RETURN
  TRANSID that named it), so no program-level model derives it.
- **The harness's fact.** The id is stated by whoever runs the task, as EIBTASKN is (X21) and the clock is (M4). The
  equivalence harness gives each case's `"transid"` to both sides: the stub driver reads it from `eib.in`
  (`{transid:<4}`, first field) and does `MOVE IN-TRNID TO EIBTRNID`; the det port's task is built with it
  (`new CicsTask(transid, ...)`) and its `runTask` does `Cobol.move(task.transid(), EIBTRNID)`. Both are a MOVE into a
  PIC X(4), so a shorter id is space padded.
- **So a proof says:** given the transaction id the case states, the port does what the COBOL does with it (GenApp's
  programs copy it into the error message header; CBSA's abend records carry it as ABND-TRANID). It does NOT say the id
  is the region's: the case's transid is the CSD name of the burned corpus's transaction for that program, chosen by the
  case author, not read from a CSD at run time.
- **Not validated (a gap, not a refusal).** The harness does not check that a transid is 1 to 4 characters or free of
  spaces. A longer one would be cut by the MOVE in the det port and would shift the stub's `eib.in` fields. Every
  burned case states a four-character id with no space (checked at the time of writing), so no burned proof depends on
  it. A case that states anything else is outside the proven set.
- **Reached.** Every CICS task of every equivalence case. A program that never reads EIBTRNID is unaffected; the row is
  `cics.convention.EIBTRNID` in register C18.

### X69. CALL ZUIDSTCK: the 16 TOD bytes are opaque and stated by the run, never the host clock (#5945, zECS ZECS001)
- **What the program does with it.** ZECS001's 4000-GET-COUNTER does `CALL ZUIDSTCK USING BY REFERENCE THE-TOD` (16 bytes, `Source/ZECS001.cbl:1244`) and
  keeps only `THE-TOD(1:6)` as ZK-ZF-IDN, the unique-ID prefix of a record key (lines 1304, 1323). ZUIDSTCK is an assembler store-clock wrapper the zECS
  estate ships no source for, so which clock instruction it issues and how it lays out the 16 bytes is not known.
- **Assumed.** ZUIDSTCK's 16 bytes are opaque; the program depends only on them being stated; their STCK/STCKE layout is not modelled.
- **IBM, as context only.** STORE CLOCK (STCK) stores an 8-byte TOD clock value and STORE CLOCK EXTENDED (STCKE) a 16-byte one (z/Architecture
  Principles of Operation, SA22-7832, https://www.ibm.com/docs/en/zos/latest?topic=instructions-store-clock-stck). These describe the instructions, not what
  ZUIDSTCK returns: no field of the 16 bytes is read as a time, an epoch or a clock-steering value.
- **What the runtimes do.** The port's `cobolrt/le/Zuidstck.java` fills THE-TOD from `$GGC_ZUIDSTCK_TOD` (or the per-task `Zuidstck.state(hex)`, which wins,
  as all scenarios share one JVM); the oracle's `tests/equivalence/le/zuidstck.c` is fed the same 32 hexadecimal digits (an unstated or malformed value
  exits 98 by name). The refusal on both: "ZUIDSTCK: a TOD the run does not state ($GGC_ZUIDSTCK_TOD, 32 hexadecimal digits) is not modelled". The same name
  called with a literal or through an identifier's value resolves to the stand-in.
- **The check (no reader of the time).** No zECS source reads ZK-ZF-IDN as a time. It appears only in ZECSZKC.cpy (the layout) and ZECS001's two MOVEs;
  ZK-ZF-KEY (the IDN plus the 2-byte NC) is used only as an opaque key. ZECS000 and ZECS003 COPY ZECSZKC but name neither field; ZECSPLT, ZECS002.asm and
  ZECSNC.asm do not name it or the copybook. A stated TOD changes key bytes only.
- **Known limit.** The stand-in answers every call of a run with the same bytes, where the real clock advances. ZECS001 has one CALL site, so the prefix
  it writes is unaffected; a program that called twice and compared would not be modelled.
- **Status and evidence.** ASSUMED. ZECS001 translates 560 of 561 statements (the one hole is the COMMAREA DTO the forge's stub does not carry, X47);
  executed-equivalent on zecs-zecs001 with two stated TODs (the `application/octet-stream` path), 0 diffs. System-copybook rule
  (mainframe-evidence-policy.md 6): nothing of IBM's or zECS's assembler is shipped. Pointer lane: X47.

### X70. File control abend injection: AFCR / AFCS / AFCT planned on a file command, the HANDLE ABEND exit takes it — ASSUMED, REFUSED where IBM is silent (#6271)
- **What IBM says** (CICS TS 6.x, abend codes AFCR, AFCS, AFCT: the VSAM RLS file control abends, https://www.ibm.com/docs/en/cics-ts/6.x?topic=codes-transaction-abend). A file control request that cannot be satisfied by the RLS server (the server is unavailable, the file has no SMSVSAM access, a timeout) ends the task with the abend code, "abnormally terminated"; it is not a RESP condition. An active `HANDLE ABEND` exit gets control, the way it does for an `EXEC CICS ABEND` (EXEC CICS HANDLE ABEND: "the task's abend exit is activated ... deactivated when it gets control").
- **Modelled** (`CicsTask.injected`, the stub's `injected_at`, the det translator's post-command check, `equivalence_cics.fault_lines`): a planned line `CMD FILE NTH -1 0 ABCODE` abends the task at that command with the code (cause "system"); the command does nothing else and answers NORMAL. The abend is recorded as the event `ABEND abcode=..` on both sides, the fired fault is logged as `CMD FILE NTH ABEND ABCODE`, a HANDLE ABEND exit at the program's level takes the task to its label (the exit is deactivated, `ASSIGN ABCODE` reads the code), an exit above a LINK unwinds the levels below, and no exit ends the task (the unit of work is backed out). A det port checks `task.abendExit()` / `task.ended()` after a file command only in a program that has a HANDLE ABEND.
- **What IBM leaves open, and what we do.** (1) Which codes: AFCR, AFCS and AFCT (the three RLS file control abends the burned estates test for) and AFCC (CICS TS 6.x, "an internal logic error ... calling the file control request module DFHFCFR": the task is abnormally terminated with a transaction dump, https://www.ibm.com/docs/en/SSJL4D_6.x/reference-abend-codes/abend-codes/AFxx_abend_codes/AFCC.html). AFCC is not a storm-drain code, so it takes a program's `EVALUATE ABCODE` none arm (CBSA INQCUST `read-abends-afcc`; the arm is the one every unnamed code takes); any other code is REFUSED. (2) Which command meets the abend: the real trigger is the RLS server, not a particular command, so a plan names the command and the Nth occurrence of it (ASSUMED); a non-file command is REFUSED. (3) RESP2: IBM states none, a plan naming one is REFUSED. (4) The state of an open browse or a held update lock after the abend: the task ends or the exit runs, and the model keeps no file lock between tasks (ASSUMED).
- **LINK (ASSUMED):** a plan `LINK PROGRAM NTH -1 0 ABCODE` abends the task at the LINK in the caller (event `ABEND`, then `LINK ... resp=0`); the callee never runs and its own HANDLE ABEND exit does not absorb the abend (a file abend inside the callee is the callee's to handle, which the file plans already cover). The abend searches the exit from the issuing level upward; a det port runs it at the task's first program level, so a LINK issued from a deeper level is not planned (ASSUMED). Proven on INQACCCU (cbsa-inqacccu: `link-inqcust-abends-afcr` / `afcs` / `afct`).
- **Browse commands (ASSUMED):** a READNEXT / READPREV that abends answers RESP 0 with no key and no record; the det runtime's `Browsed.normal()` / `BrowsedRba.normal()` are false for it, so a port never reads the record before it checks the exit. Proven on INQCUST (cbsa-inqcust: `read-abends-afcr`, `startbr-abends-afcs`, `readprev-abends-afct`: the storm-drain arm of ABEND-HANDLING answers 'N' / '2'; `read-abends-afcr-rollback-fails`: the SYNCPOINT ROLLBACK fails INVREQ (X71), so the arm LINKs ABNDPROC and ABENDs HROL CANCEL).
- **Refused by name:** the list in the summary. None of the twelve burned programs that hold a HANDLE ABEND issues a COBOL CALL, so an abend of a CALLed program is refused (nothing to prove). An abend of a non-file CICS command other than the LINK above is refused too; ZECS000's `9100-ABEND` exit is reached by a file abend on its control READ (zecs-zecs000: `control-read-abends-afcr` / `afcs` / `afct`), so no non-file abend is needed. Db2 AD2Z is X73.
- **Status:** ASSUMED for the command it is planned on and the unit-of-work backout, REFUSED where listed. The oracle is GnuCOBOL plus our stub, not z/OS. Unit-proven (tests/tools/test_equivalence_cics_abend_injection.py) and proven on COCRDUPC (carddemo-cardupdate: `search-card-read-rls-abend-afcr`, `pf5-rewrite-rls-abend-afct`).

### X71. RESP faults on SEND MAP, SEND TEXT, RECEIVE MAP, RETURN, SYNCPOINT and SYNCPOINT ROLLBACK: the conditions IBM documents, planned per scenario — ASSUMED, REFUSED where IBM is silent (#6271)
- **What IBM says** (CICS TS 6.x, the Conditions of https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-map, `-receive-map`, `-return`, `-syncpoint`, `-syncpoint-rollback`). SEND MAP: IGREQCD 57, IGREQID 39, INVLDC 41, INVMPSZ 38 (the map is too wide or too long for the terminal), INVPARTN 65, INVREQ 16 (RESP2 200: not allowed for a DPL server program; also raised with no RESP2), OVERFLOW 40, RETPAGE 32, TSIOERR 35 (irrecoverable temporary storage I/O error), WRBRK 3. Only INVREQ lists a RESP2. SEND TEXT (https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-text): IGREQCD 57, IGREQID 39, INVLDC 41, INVPARTN 65, INVREQ 16 (RESP2 200: not allowed for a DPL server program; also raised with no RESP2), LENGERR 22 (LENGTH out of range), RETPAGE 32, TSIOERR 35, WRBRK 3; planned: TSIOERR, INVREQ RESP2 200, LENGERR (no RESP2 for either), the rest refused (BMS partitions, LDCs, paging, SIGNAL, 2741). SEND CONTROL lists the same minus LENGERR (sibling gap). RECEIVE MAP: EOC 6, EODS 5, INVMPSZ 38, INVPARTN 65, INVREQ 16 (issued in a nonterminal task), MAPFAIL 36, PARTNFAIL 66, RDATT 2, UNEXPIN 49; no RESP2 values given. RETURN: CHANNELERR RESP2 1; INVREQ RESP2 1 (TRANSID in a program with no terminal), 2 (CHANNEL / COMMAREA / IMMEDIATE not at the highest logical level), 4 (TRANSID in an APPC program), 8 (INPUTMSG), 30 (first-stage PLT), 200 (INPUTMSG with DPL), 203 (remote region lacks channel support); LENGERR RESP2 11 (COMMAREA length < 0 or > 32763), 26 (COMMAREA address zero with a non-zero length), 27 (INPUTMSG length). SYNCPOINT: INVREQ RESP2 200 (linked to from a remote system without SYNCONRETURN, or EXECUTIONSET=DPLSUBSET); ROLLEDBACK 82 (a remote system that cannot commit drove the unit of work into rollback; no RESP2; all changes backed out).
- **Modelled** (`equivalence_cics.fault_lines` / `UI_FAULT_CONDITIONS`, the stub's `injected_at` in GGCSMAP / GGCRECV / GGCRETI / GGCSYNC, `CicsTask.planned` and `returnImmediate`, the det translator's SEND MAP / RECEIVE MAP / SYNCPOINT outcome): a planned line `CMD NAME NTH RESP RESP2` makes the Nth occurrence of the command answer that RESP / RESP2 (`NAME` the map for SEND-MAP and RECEIVE-MAP, `-` for SEND-TEXT, RETURN, SYNCPOINT and ROLLBACK). RESP, RESP2 and EIBRESP are written as CICS writes them, a command that codes no RESP raises the condition (HANDLE CONDITION), and the failed command does nothing else.
- **What IBM leaves open, and what we do.** (1) What a failed command leaves behind: IBM does not say. ASSUMED: SEND MAP sends nothing (no SEND-MAP event, the screen is as it was); SEND TEXT likewise sends nothing (no SEND-TEXT event; CONVERSE's own write consults no SEND TEXT plan); RECEIVE MAP leaves INTO untouched; SYNCPOINT / SYNCPOINT ROLLBACK takes no syncpoint and ends no unit of work (no event, the next one still holds the changes); a failed RETURN goes on in the program (as the existing failure of RETURN IMMEDIATE does, #4270). (2) A RESP2 where IBM states none (INVMPSZ, TSIOERR, RECEIVE MAP's conditions): a plan naming one is REFUSED. (3) A condition that IBM lists with several RESP2 values: the plan names one of them. (4) Which RETURN forms a planned condition applies to: RETURN IMMEDIATE and the plain RETURN's failure path share `returnImmediate`; a plain RETURN TRANSID that codes RESP (BNKMENU line 178) is planned too (GG-ITEM 2 in the stub, `CicsTask.returnTransidResp`): a fault there leaves the task running and passes nothing on. A plain RETURN that codes no RESP never consults the plan (IBM does not describe the abend it would take): a plan aimed at it stays unfired and the run fails "planned fault never fired".
- **Refused by name:** IGREQCD, IGREQID, INVLDC, INVPARTN, OVERFLOW, RETPAGE, WRBRK, EOC, EODS, PARTNFAIL, RDATT, UNEXPIN, CHANNELERR, ROLLEDBACK, and RETURN INVREQ RESP2 8 / 30 / 203, LENGERR RESP2 on INPUTMSG with no INPUTMSG operand: each needs a device, a partition, BMS paging, a remote system, a PLT stage or an operand the case does not model. MAPFAIL stays natural (RECEIVE MAP with no input). SEND TEXT is planned (below). SEND CONTROL is refused by name: IBM lists its conditions (SEND TEXT's minus LENGERR), but every burned caller (BNKMENU, BNK1CAC, BNK1CCA, BNK1CRA, BNK1DAC, BNK1UAC, BNK1DCS) codes it with no RESP and goes straight to RETURN, IBM does not describe the abend a failure would take, and so no failure arm exists to reach; a plain SYNCPOINT that codes no RESP (CardDemo COPAUS0C line 686, COPAUS1C line 558) is the same case (a plan aimed at it stays unfired). Guarded by test_no_burned_cbsa_send_control_codes_resp.
- **Status:** ASSUMED for the state a failed command leaves, REFUSED where listed. The oracle is GnuCOBOL plus our stub, not z/OS. Unit-proven (tests/tools/test_equivalence_cics_fault_resp.py) and proven on CBSA BNKMENU (`option-*-return-invreq`, `first-entry-send-map-invmpsz`, `mapfail-dataonly-send-map-tsioerr`, `receive-map-invmpsz`) and DBCRFUN (`proctran-insert-fails-rollback-invreq`), and CBSA BNK1UAC and BNK1CRA (`first-entry-send-map-invmpsz`, `bad-type-send-map-tsioerr` / `bad-sign-send-map-tsioerr`: the SEND MAP failure arms behind SM010 lines 1083, 1235, 657 and 806, whose "no fault can be injected" entries are gone), and the plain form on BNKMENU (`first-entry-plain-return-invreq`, `invalid-action-plain-return-invreq`: A010 line 178 true, 46 -> 47 of 62 branches). The SEND TEXT failure arm of SEND-TERMINATION-MSG (STM010; scenario `pf12-send-text-tsioerr`) is reached on BNKMENU, BNK1CAC, BNK1CCA, BNK1CCS, BNK1CRA, BNK1DAC, BNK1TFN and BNK1UAC, and the plain RETURN TRANSID failure arm of A010 (`first-entry-plain-return-invreq`, INVREQ RESP2 4) on the seven BNK1* programs; their "no fault can be injected" infeasible entries are gone, the RETURN false arms (a successful RETURN ends the task) stay stated infeasible.

### X72. RESP faults on DELAY: EXPIRED and INVREQ, planned per scenario — ASSUMED, REFUSED where IBM is silent (#6271)
- **What IBM says** (CICS TS 6.x, the Conditions of https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-delay). EXPIRED 31 (the time specified in the request had already expired when the request was issued; no RESP2 given). INVREQ 16, RESP2 4 (the INTERVAL / TIME / FOR / UNTIL value is invalid for the form used), 5 (the request is not valid with the options given), 6 (a FOR / INTERVAL value is out of range), 22 (the REQID is invalid). NORMAL, RESP2 23: the delay was cancelled by another task (CANCEL).
- **Modelled** (`equivalence_cics.fault_lines` / `UI_FAULT_CONDITIONS`, the stub's `injected("DELAY", "-")` in GGCDLAY, `CicsTask.planned` in the det translator's `delay()`): a planned line `DELAY - NTH RESP RESP2` makes the Nth DELAY answer that RESP / RESP2. RESP, RESP2 and EIBRESP are written as CICS writes them, a DELAY that codes no RESP raises the condition (HANDLE CONDITION), and the failed DELAY does nothing else.
- **What IBM leaves open, and what we do.** (1) What a failed DELAY leaves behind: IBM does not say. ASSUMED: nothing is performed — no child task is dispatched, the simulated clock does not move, no POST is released; the program goes on after the command. EXPIRED's default action when unhandled is to ignore it. (2) A RESP2 where IBM states none (EXPIRED): a plan naming one is REFUSED. (3) INVREQ lists four RESP2 values: the plan names one. (4) Natural out-of-range DELAY values (a FOR / INTERVAL the program computes) are still not turned into INVREQ by the stub: a sibling gap.
- **Refused by name:** NORMAL RESP2 23 (cancel by another task: needs a second task), and every condition IBM does not list for DELAY (SYSIDERR, ISCINVREQ, and the like).
- **Status:** ASSUMED for the state a failed DELAY leaves, REFUSED where listed. The oracle is GnuCOBOL plus our stub, not z/OS. Unit-proven (tests/tools/test_equivalence_cics_fault_resp.py) and proven on CBSA CRDTAGY1-5 (`delay-invreq-seconds-out-of-range`, which reaches the A010 failure branch: ASSIGN, POPULATE-TIME-DATE, LINK ABNDPROC, ABEND).

### X73. Db2 abend injection: AD2Z planned on a -911 statement, the HANDLE ABEND exit takes it — ASSUMED, REFUSED where IBM is silent (#6271)
- **What IBM says** (CICS TS 6.x, abend code AD2Z, https://www.ibm.com/docs/en/cics-ts/6.x?topic=codes-transaction-abend). A Db2 deadlock or timeout makes the CICS-Db2 attach attempt a syncpoint rollback (DROLLBACK(YES)); when that rollback fails the attach writes DFHDB2070 and the task abends AD2Z with a dump. An active `HANDLE ABEND` exit gets control, as for an `EXEC CICS ABEND` (X70).
- **Modelled** (`equivalence_cics.sql_fault_plan` / `mark_sql_abends`, the stub's `GGCSQLAB`, the det translator's `det/sql.py` check): the SQL fault is planned as before (`PROGRAM LINE NTH -1 SQLSTATE`), and a second plan line `SQL PROGRAM:LINE NTH -1 0 AD2Z` is read by the CICS side. After the statement's own call, a marker (COBOL side) or a `task.planned("SQL", "PROGRAM:LINE")` check (Java side, only in a program that has a HANDLE ABEND) raises the abend at the Nth execution of that statement, before the program's WHENEVER tests. The event `ABEND abcode=AD2Z cause=system` is recorded on both sides; the HANDLE ABEND exit deactivates, an exit above a LINK unwinds the levels below.
- **What IBM leaves open, and what we do.** (1) Which SQLCODE: only -911 (deadlock, rollback done) is tied by IBM to the failed-rollback path; every other SQLCODE is REFUSED. (2) Whether the rollback fails is not decided by the statement: the plan states it (ASSUMED). (3) The SQLCA after the abend: the program's exit reads what the failed statement left (-911 / 40001, SQLERRD and SQLERRMC as the fault declares them); IBM does not say the attach leaves it untouched (ASSUMED). (3b) The deadlock token: the COBOL AD2Z arm reads `SQLERRMC(1:SQLERRML)`, so a scenario must declare `sqlerrmc`; the cases use `00C90088`, the Db2 deadlock reason code, which is an ASSUMED stand-in (libcob raises a bounds error on a zero length). (4) The statement: named by its source line, because a table-and-verb selection can match several statements and the nth counts of the two plan lines must agree (REFUSED).
- **AD2R / AD2X (#6271):** IBM (CICS TS 6.x abend codes AD2R: "the CICS-DB2 attached TCB connection that processes the DB2 request ... has abended"; AD2X: "the CICS and the thread TCB were in an invalid state"; both: "the task is abnormally terminated with a transaction dump", https://www.ibm.com/docs/en/SSJL4D_6.x/reference-abend-codes/abend-codes/ADxx_abend_codes/AD2R.html and .../AD2X.html). They are not tied to a SQLCODE or to a failed rollback, so the plan names the statement by `line` and any SQLCODE (the SQLCA the exit reads is ASSUMED, as for AD2Z). Both take a program's `EVALUATE ABCODE` none arm: proven on DBCRFUN (`update-attach-abends-ad2x` / `ad2r`), INQACC and INQACCCU (`open-attach-abends-ad2x`). Other AD2x codes stay REFUSED (no program tests for them).
- **Refused by name:** the list in the summary. Abends of a LINKed or CALLed program and of non-file commands are not planned here (#6271 remaining slices).
- **Status:** ASSUMED for the SQLCA left behind and the unit-of-work backout, REFUSED where listed. The oracle is GnuCOBOL plus our stub, not z/OS. Unit-proven (tests/tools/test_equivalence_sql_abend_injection.py) and proven on DBCRFUN (cbsa-dbcrfun: `update-deadlock-abends-ad2z`), XFRFUN, and INQACCCU's cursor statements (cbsa-inqacccu and cbsa-inqacccu-generated: `open-deadlock-abends-ad2z` on the OPEN, `fetch-deadlock-abends-ad2z` on a FETCH inside the loop; the generated rows give customer 1 fewer than two accounts, so its FETCH abend is the first FETCH, the hand case's the second). A cursor OPEN, FETCH and CLOSE are one mechanism with an UPDATE: the plan names the statement by line. Coverage of INQACCCU: 18/22 paragraphs, 23/33 branches (was 16/22, 21/33); the ABNDPROC link now runs.

## Language Environment

### L1. CEEDAYS — MATCHED where documented, a blank picture tail and the slack past an item ASSUMED, REFUSED otherwise
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
  lies past the picture item (a declared length that overruns it) is the slack ruled below.
- **Refused (exit 98).** A picture tail with any non-blank byte (`'YYYYMMDDX'`, `'YYYYMMDD00'`, a complete set of
  tokens followed by more tokens), also when the declared length then overruns the item (the byte inside the item is
  what is refused). A numeric month outside 1–12 (2508 vs 2517: IBM documents CEE2517 for a month not recognized
  but not what a numeric 13 is); a trailing blank on the part of the date the picture covers (whether it is 2507 or 2520, #4049;
  a blank inside it is a non-numeric position, 2520, and date bytes past the span are ignored); `YY` (a century window), month names, eras, a null or blank picture, a repeated or
  incomplete picture, a blank or mixed separator, `DDD` together with `MM` or `DD`.
- **Broadened by #4952.** CardDemo's `'YYYYMMDD  '` (picture and date padded with blanks to 10) used to be refused as a
  picture inside a longer field; it is modelled now (the span is read, the blank tail ignored), which is the assumption
  above and nothing wider. The test table is `tests/cobol_mainframe/test_det_ceedays.py`.
- **Swept across the burned estates (#5003).** The LE date/time callers there are CardDemo CSUTLDTC (CEEDAYS), CBSA CRECUST
  (CEEDAYS) and CBSA BANKDATA (CEEGMT, CEEDATM). CRECUST is the only vstring whose declared length passes its text (10
  over `PIC X(8)`); CSUTLDTC sets the length from `LENGTH OF` the format item and BANKDATA's CEEDATM picture is 14 over 14.
  `test_only_cbsa_crecust_declares_a_vstring_length_past_its_text` pins that. IBM reads the declared length, so the 2
  bytes are the slack after the `01` item, whose content IBM does not specify. **Assumed (owner decision 2026-10-23).**
  Nothing statically known occupies them: the next `01`, `DATE-OF-BIRTH-FOR-CEEDAYS`, is a separate level-01 (doubleword
  aligned, so the slack is alignment padding), and neither item has a `VALUE` for it. The slack is ruled BLANK, the same
  assumption as the blank tail above, for storage the program never wrote. The det runtime skips every byte past the
  picture item by its bound; the C model cannot see the item's end, so it reads the NUL padding cobc leaves after a `01`
  item as that slack (a NUL byte inside a picture is not COBOL text). A non-blank byte INSIDE the item is still refused.
  The feedback token `FC` is 12 bytes (L4), so nothing overruns there.
- **BNK1CCS (#5089).** Its create-customer and born-in-the-future ENTERs reach CRECUST's CEEDAYS call and run on the slack ruling: they live in cbsa-bnk1ccs and cbsa-bnk1ccs-generated (the separate `cbsa-bnk1ccs-create` case is gone), proven with cbsa-crecust (det port equal to the oracle; X18 stays ASSUMED). The generated ENTERs still draw dates before 1601 only.
- **COACTUPC (#6271).** `EDIT-DATE-LE` passes the 8-byte `WS-EDIT-DATE-CCYYMMDD` and the 8-byte `WS-DATE-FORMAT` to
  CSUTLDTC, whose LINKAGE items are 10 bytes. Unlike CRECUST's slack this is not unspecified storage: the two bytes
  after the picture are the first two of `WS-DATE-VALIDATION-RESULT`, which `EDIT-DATE-LE` INITIALIZEs (blanks) just
  before the call, so the blank-tail assumption above covers them with real blanks and no new ruling; the date's two
  extra bytes lie past its span, which IBM ignores. Cases `edit-dates-valid` and `edit-dob-in-the-future` reach the
  call. The program's own `WS-VALID-MONTH` check refuses a month outside 1-12 before CEEDAYS, so the 2508-vs-2517
  refusal is never hit there; a date the program accepts but CEEDAYS refuses (2508, 2513) is unreachable: the program
  checks the century (19 or 20), the day of month and the leap year itself.

### L2. CEE3ABD — MATCHED
- `ggabend.c` records `ABEND Unnnn`, and the Java side's CobolAbend gives the same.
- **IBM.** z/OS Language Environment Programming Reference (SA38-0682), CEE3ABD (terminate enclave with an abend):
  `CALL 'CEE3ABD' USING abcode, timing` ends the enclave with a user abend; `abcode` is a fullword binary user
  completion code and `timing` says whether LE cleanup runs first. The step then ends `ABEND Unnnn`, with no return
  code.
- **Declared difference.** GnuCOBOL has no CEE3ABD, so `ggabend.c` stands in for it: it records `U%04d` (the code
  modulo 4096, as a user completion code is) and exits. `timing` is not modelled (LE cleanup is not run); the abend
  code is the only thing compared. The reason code and any dump are not produced.
- **Declared difference (#6072).** A bare `CALL 'CEE3ABD'` with no `USING` (CardDemo's CBSTM03A `9999-ABEND-PROGRAM`) has
  no `abcode`: IBM's documentation defines only the two-parameter form, so the code is undefined there. `ggabend.c` reads
  libcob's call-parameter count and records `U0000` for it, as the Java side does; what is compared is that the step
  abends, not a code IBM does not define. A z/OS run of that step would show the real code; none has been made.

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
- **IBM.** The Enterprise COBOL for z/OS Language Reference (VALUE clause) leaves the initial contents of a data item
  with no VALUE clause undefined; the Language Environment Programming Reference's STORAGE runtime option (IBM default
  `NONE,NONE,NONE,0K`, i.e. no initialisation) decides what the storage held.
- **Declared difference.** The oracle's spaces (zeros in a numeric DISPLAY item) are a declared oracle-vs-IBM
  difference, not a match: IBM defines no value there. No proof rests on a byte IBM leaves undefined beyond the two
  bytes and the `WS-CONT-IN` tail above (C18 applies the same stated difference).

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

### L6. CEEGMT / CEEUTC, CEEDATM, CEESECS, CEEDATE, CEEISEC, CEESECI, CEEDYWK, CEEQCEN, CEESCEN — IBM's conditions where documented; the clock, the output item and what IBM leaves open assumed or refused
- **What IBM documents** (Language Environment Programming Reference, the callable services; the message lists below are
  those IBM publishes for the same services as the ILE CEE APIs, which share their definitions and message numbers:
  https://www.ibm.com/docs/en/ssw_ibm_i_73/apis/CEEDATM.htm, `CEESECS.htm`, `CEEDATE.htm`, `CEEISEC.htm`, `CEESECI.htm`, `CEEDYWK.htm`, `CEEUTC.htm`
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
  - **CEESECI** `(input_seconds, year, month, day, hours, minutes, seconds, milliseconds, fc)` (#5003, the inverse
    of CEEISEC): input valid 86 400 to 265 621 679 999.999; on an invalid value every output is 0 and the code is
    CEE2505 (the seconds are out of range).
  - **CEEDYWK** `(input_Lilian_date, day_number, fc)` (#5003): day_number 1 (Sunday) to 7 (Saturday), a fullword;
    valid 1 to 3 074 324; day_number is 0 on an invalid date and the code is CEE2512 (not CEE2513, which is
    CEEISEC's and CEESECS's). IBM's page gives no sample: day 1 (15 October 1582) was a Friday, 148 138 a Monday.
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
  oracle's case clock is read as GMT; a zone is not modelled: CEEGMTO / CEEUTCO answer an offset of zero (#5003, below). (2) Output_timestamp and
  output_char_date (CEEDATM, CEEDATE) are halfword-prefixed VSTRINGs in COBOL: the model writes the length then the
  text and touches nothing past it; a failing call writes a zero length and leaves the text. IBM says the output is
  blanks on error and cut to the output's length (CEE2526 / CEE2527) but states no COBOL layout for an output declared
  `PIC X(n)`, as BANKDATA's `DATM-CONV` is (it reads `DATM-CONV(1:14)` only in a debug line). Both sides refuse an
  output item shorter than the result, so 2526 / 2527 are never produced. The Java side knows the item's size. The C model is handed a bare pointer (GnuCOBOL passes no size to a CALLed C routine), so the harness reads the program's DATA DIVISION (`tests/tools/le_out_size.py`) and gives the model `GG_LE_OUT_SIZES=CEEDATE=n,CEEDATM=n`; a result longer than the item is then refused by name (exit 98), the smallest resolved item of a service's calls counting. An item the harness cannot size exactly (COPY or LINKAGE member, REDEFINES, OCCURS, non-DISPLAY usage, subscript, a name declared twice) is left unchecked on the C side, and the census test (below) is what keeps a burned program from reaching it. `test_det_le_time.py` pins both sides: for CEEDATE and CEEDATM an item one byte short of 2 + the result is refused, one of exactly that size is filled whole, byte for byte equal across the two.
  (3) The milliseconds of a Lilian second are the fraction floored to a thousandth, so a value in `.9995` is `.999`;
  a seconds value is valid below 265 621 680 000. (4) CEESECS answers CEE2525 (picture mismatch) for a non-digit in
  a numeric position or a delimiter that differs from the picture's: IBM names the code, not its trigger. (5) A
  value that is not exact in both HFP and IEEE (`.12`) can differ in the last bits; only the millisecond is compared.
- **Refused (exit 98, "NAME: ... is not modelled"), because IBM leaves it open or the model has no rule for it.**
  A picture with names (`Mmm`, `Www`), `AP`, Z-suppression, eras (`<JJJJ>`, `<CCCC>`), `RRRR`, a lone `Y` / `M` /
  `D` / `H` / `S` / `9`, a repeated token, or none (IBM: the country default). CEEISEC and CEESECS with **more than
  one** invalid field (IBM lists the codes, not their order). CEESECS: a timestamp shorter than its picture (IBM
  lists no insufficient-data code for it), with a leading blank, with leading zeros omitted after a delimiter
  (`1988-5-16`: IBM accepts it; the model has no rule), `DDD` in the input, or a picture without a full date.
  CEEGMT, and CEESECS with a `YY` in its picture, without a pinned clock.
- **Modelled (#5003), assumed (6).** CEEGMTO / CEEUTCO (the same service) return hours 0, minutes 0, seconds 0.0 and a
  success feedback code. The time-zone decision: the clock is GMT (CURRENT-DATE ends `+0000`), so local time is GMT and
  the offset is zero; no zone table. `test_the_zero_offset_is_the_clocks_offset` ties the two, so a zoned clock cannot
  land without revisiting this service. Residual risk: a program that branches on a nonzero offset sees zero; no burned
  program calls either name.
- **Modelled (#5003): CEESECI and CEEDYWK** (`LeTime.seci` / `LeTime.dywk`, thin classes `Ceeseci` / `Ceedywk`, the
  C twin in `le_time.c`), one vector table through both sides: every documented condition (CEE2505; CEE2512), the
  bounds (86 400; 265 621 679 999.5; Lilian 1 and 3 074 324), every weekday, a century year that is not a leap year,
  and CEESECI fed the output of every CEEISEC row. Assumed: the milliseconds are floored as for CEEDATM (3); a
  fraction that is not exact in binary can differ by one millisecond between HFP and IEEE (5), so the vectors use
  exact ones. Neither service has a picture or a field combination to refuse.
- **Modelled (#5003): CEESCEN** (`CALL 'CEESCEN' USING century_start, fc`, translated to `Ceeqcen.set`, charset last, `gen.LIBRARY` /
  `LIBRARY_CHARSET`; `tests/cobol_mainframe/test_det_le_time.py` pins the arity and the emitted call). The setting is one value shared with
  CEEQCEN (default 80); 0 to 100 is stored, anything else is CEE2533 and the setting is kept. Assumed: the setting lasts the run (a
  CEESCEN in one program is seen by a later CEEQCEN in another). No burned program calls CEESCEN.
- **Modelled (#5003), assumed (7): the century window of CEESECS.** A `YY` in the picture is the year in the 100-year window
  that starts `century_start` years before the system year (CEEQCEN's 80 until CEESCEN sets it): with system year S and
  start c, the first year is S - c and `YY` is the one year in [S - c, S - c + 99] with those last two digits (2026, 80:
  1946 to 2045, so 88 is 1988 and 45 is 2045; start 0: 2026 to 2125; start 100: 1926 to 2025). The system year is the
  run's pinned clock (the det runtime's CURRENT-DATE, the oracle's `COB_CURRENT_DATE`), so without one a `YY` is refused by
  name. Assumed: the window is placed by the year alone, not by the month or day (IBM's page gives the window in whole
  years). The year found goes through CEEISEC's checks (a 29 February in a window year that is not a leap year is CEE2508).
  Vectors: both sides, the start 0 / 50 / 80 / 100, an invalid start kept, two clocks, a year-boundary pair for each. `DDD`
  stays refused.
- **Not modelled: sibling services** of the same set: CEEFMDA / CEEFMDT / CEEFMDV (a call is refused by name by the translator, as before), and the
  country-default (null) pictures. A null picture (a zero-length picture string) is refused on both runtimes for all three
  services, one vector each in `test_det_le_time.py` (CEEDATE, CEEDATM, CEESECS: exit 98, "a null picture (IBM takes the country
  default)"). Not modelled because the default is IBM's locale table (a country code, which this model does not carry) and the oracle
  has no such table to prove it against, so a guessed picture could not be checked; no burned program omits a picture (next bullet). Settled for the burned estates (#5003 [c:51f133ad]): the refusal is the final state until a burned program omits a picture; the census test fails first when one does, and the default is then modelled with IBM's table and an oracle to check it.
- **IBM references.** The pages above; CEELOCT's example (L5) and the symbolic feedback codes (L4).
- **Not modelled, no burned program needs them (#5003).** CEEFMDA / CEEFMDT / CEEFMDV and null (default) pictures; CEE2526 / CEE2527
  truncation is refused on both sides (above) (CEESECI and CEEDYWK are modelled, above). A sweep of the burned estates finds no call to any of them (CRECUST and CSUTLDTC call CEEDAYS, BANKDATA CEEGMT and
  CEEDATM with a 14-byte picture and an 80-byte output), so there is nothing to prove; they stay refused by name (the CALL is a hole that names the service). `tests/cobol_mainframe/test_le_fmd_census_5003.py` pins the census: it fails when a burned source calls CEEFMDx, omits a picture, or writes an output shorter than the picture's result, and when the translator stops refusing CEEFMDx.

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
- **MVSWAIT (#5106).** CardDemo's `app/asm/MVSWAIT.asm` (CALLed by COBSWAIT) is modelled the same way
  (`tests/equivalence/le/mvswait.c`, `Mvswait.java`): it loads its fullword argument, starts an interval timer and
  returns with R15 = 0, writing nothing to the caller. The wait is not observable in a compared output, so it is not
  slept; an argument shorter than the fullword is refused on the Java side.

- **IBM (document).** The instructions the translation reproduces are defined in the IBM z/Architecture Principles of
  Operation (SA22-7832): MVC moves the bytes of the length coded (length code plus one), and CLC compares operand 1's
  length of bytes against operand 2, so an operand 1 with no explicit length takes the length of its symbol, here 20
  bytes, against a 1-byte literal. High Level Assembler for z/OS Language Reference (SC26-4940) gives the default
  length of an operand written without one. The wording is paraphrased, not verbatim.
- **Declared difference.** The oracle is not the assembler and not z/OS: the COBOL side runs a C translation of the
  routine, the Java side another, both written from the source. The paths whose result rests on the load module's
  literal pool are refused (exit 98), not matched; the modelled path (type `'2'` to `'2'`) moves bytes the source names.

### A2. z/OS control blocks (PSA / TCB / TIOT) — laid from the job step the run states
- **What.** CardDemo's CBSTM03A walks z/OS control blocks to DISPLAY its job, step and DD names: a POINTER never set
  (NULL, the PSA at address 0) addresses the PSA, `PSATNEW` gives the current TCB, `TCBTIO` gives the TIOT, and a
  POINTER over a BINARY counter steps through the TIOT's DD entries until a zero fullword. Nothing in the source
  decides what those blocks hold; the job step does. Like X68's EIBTRNID, the step is a stated fact of the run (the
  case's), here the system property `gitgalaxy.mvs.step`, in the form `JOB;STEP;PROCSTEP;DD:UCB,DD:NOUCB,...`
  (the three header names in the TIOT's order, then each DD in JCL order, `UCB` for a data set DD, `NOUCB` for
  SYSOUT / DUMMY / in-stream).
- **IBM.** z/OS MVS Data Areas (ibm.com/docs/en/zos, the PSA, TCB and TIOT data areas): PSA (`PSATNEW` at X'218'), TCB (`TCBTIO` at offset 12), TIOT (a 24-byte header,
  `TIOCNJOB` / `TIOCSTPN` / `TIOCJSTP`, then one entry per DD: `TIOELNGH` 20 for a single-unit DD, `TIOEDDNM` at +4,
  the UCB token `TIOEFSRT` at +17..19; the list ends at a zero fullword).
- **Modelled (det runtime `DetMvs.java`, rule RT-MVS-CONTROL-BLOCKS).** Three blocks addressed by 8-byte handles
  (C9; block in the high word, offset in the low): the PSA (544 bytes, `PSATNEW` holding the TCB handle), the TCB
  (20 bytes, `TCBTIO` holding the TIOT handle), the TIOT laid from the stated step. `SET ADDRESS OF` a whole 01 to
  a pointer, `SET ptr1 TO ptr2`, and ADD / SUBTRACT / `COMPUTE v = v +/- n` on the BINARY a POINTER REDEFINES
  (or on X47's view) move through them.
- **Assumptions.** `PSATNEW` is the program's own TCB while it runs; only the bytes the walk reads are laid (every
  other byte is zero); a DD is single-unit (20-byte entry) and the TIOT holds no JOBLIB / STEPLIB-from-JOBLIB or
  dynamically allocated entries beyond those stated; the UCB token is nonzero exactly for a data set DD; pointers
  are 8 bytes (C9), so `PSATOLD` at X'21C' is not laid.
- **Refused by name (run time).** No step stated, or one without its four fields; a DD that is not `NAME:UCB` /
  `NAME:NOUCB` or whose name is longer than 8; a record laid past the fields the stand-in lays (a zero-DD step's
  TIOT entry); pointer arithmetic that leaves its block; a pointer to no block the stand-in lays. `SET ADDRESS OF x
  TO ADDRESS OF y` and `SET ptr TO ADDRESS OF x` stay translator holes in a batch program.
- **Oracle (tests/equivalence/le/ggtiot.c, tests/tools/equivalence_mvs.py).** GnuCOBOL has no PSA at address 0 and a
  4-byte BINARY cannot overlay its 8-byte POINTER, so the harness lowers the program and links a C stand-in that lays
  the same three blocks (real pointers: `PSATNEW` to the TCB buffer, `TCBTIO` to the TIOT buffer) from the case's
  `mvs_step` (env `GGMVS_STEP`, same grammar and refusals as `DetMvs.build`). The lowering: a plain POINTER only ever
  the source of `SET ADDRESS OF` gets `CALL "GGPSAPTR"` (NULL is the PSA); every `SET ADDRESS OF rec TO ptr` is
  preceded by `CALL "GGMVSCHK" USING ptr BY VALUE LENGTH OF rec`; `ptr REDEFINES view POINTER` becomes a standalone
  POINTER (the numeric `view` is dropped) and `COMPUTE view = view +/- n`, `ADD n TO view`, `SUBTRACT n FROM view`
  (`n` a signed integer or `LENGTH OF id`) become `CALL "GGTIOTADV"` / `"GGTIOTSUB"`. Any other use of `view`
  (MOVE, IF, `*`, ROUNDED, SIZE ERROR, GIVING, a second REDEFINES) is refused by name, as the translator refuses it,
  and so is a program that walks the blocks in a case with no `mvs_step`. A refusal inside the C side is
  `GGTIOT: ... is not modelled`, exit 98. Checked: the C blocks equal `DetMvs.build`'s byte for byte over 23 steps
  (test_mvs_oracle_5856.py), and the lowered walk prints on GnuCOBOL what the det port prints.
  Limit: a pointer into no laid block is let through by `GGMVSCHK` (the C side cannot tell it from another lane's
  pointer); the det side refuses it. The CBSTM03A equivalence case is slice 3 of #5856.

## Db2 (`equivalence_sql.py`, `ggsql.c`, `DetSql`)

### Q1. Db2 for Linux, not z/OS — ASSUMED
- **What.** Both sides run their SQL on Db2 Community Edition (Db2 for LUW). The SQLCODEs these programs meet from Db2 (0, +100,
  -803, -811, -532) are the same codes on z/OS. SQLERRMC tokens come from Db2 itself.
- **Not compared to z/OS.** SQLSTATE subclasses, SQLERRD values beyond the row count, SQLERRP, and the dialect
  differences of other statements.
- **IBM.** The Db2 for z/OS Codes reference defines SQLCODE +100 (no row), -803 (duplicate key), -811 (more than one
  row from a SELECT INTO) and -532 (a delete rule restricts); Db2 for LUW uses the same SQLCODE numbers for these.
- **Declared difference.** Db2 for LUW is the oracle's engine and z/OS is IBM's: the SQLSTATE subclasses, SQLERRD
  beyond the row count and SQLERRP above are a declared oracle-vs-IBM difference, uncompared.

### Q1a. A binary host variable takes what its bytes hold — MATCHED (#4579)
- **What.** SELECT INTO / FETCH INTO a COMP / COMP-4 / BINARY / COMP-5 host variable gives SQLCODE -304 only for a value
  outside its halfword / fullword / doubleword (Db2 types the host variable by its data type: S9(9) COMP is INTEGER), not
  beyond its PICTURE's digits: 2147483647 into `S9(9) COMP` is assigned. That holds under TRUNC(STD) too; STD limits
  COBOL's own MOVE / arithmetic (C1), not the SQL assignment. ggsql.c `num_store` and DetSql (`Cobol.storeHostChecked`) agree.
- **IBM.** Db2 12 for z/OS Codes, GC27-8847-02 (ibm.com/docs/en/SSEPEK_12.0.0/pdf/db2z_12_codesbook.pdf), and Db2 10 for z/OS Codes, SQLCODE -304 (SQLSTATE 22003): "A VALUE WITH DATA TYPE data-type1 CANNOT BE ASSIGNED TO A
  HOST VARIABLE ... the host variable with data type data-type2 was not large enough to hold the retrieved value". The test
  is the host variable's Db2 data type (halfword, fullword, doubleword), as here. Db2 13 FETCH (SQL Reference, ibm.com/docs/en/db2-for-zos/13?topic=statements-fetch): "If an
  assignment error occurs, the value is not assigned to the target and no more values are assigned to targets."
  The statement that STD does not apply is ours: the cited pages do not mention TRUNC. Not measured on z/OS (#4702 Part 2).

### Q1b. A datetime host variable Db2 rejects: -180 / 22007 on both sides — MATCHED (#4658)
- **What.** An UPDATE binding an unset (non-date) PIC X host variable to a DATE column gets SQLCODE -180, SQLSTATE 22007
  ("the string representation of a datetime value is not valid") from Db2 for LUW, and the same on z/OS Db2 (-180 is the
  documented SQLCODE for this, SQLSTATE 22007). IBM's JDBC driver refuses some such values on the client with its own
  -4220 (conversion error) before Db2 sees them; that code is never a Db2 SQLCODE an embedded-SQL program meets, so
  DetSql maps it to -180 / 22007. Other driver errors pass through unchanged. SQLERRMC/SQLERRD of the mapped error stay
  empty (the DISPLAYed SQLERRD(3) is 0 on both sides).
- **IBM.** Db2 for z/OS Codes (GC27-8847-02, ibm.com/docs/en/SSEPEK_12.0.0/pdf/db2z_12_codesbook.pdf; paraphrased), SQLCODE -180, SQLSTATE 22007: "The length or string representation of a DATE, TIME, or
  TIMESTAMP value does not conform to any valid format." The -4220 mapping is ours (a driver code, not a Db2 SQLCODE).
  SQLERRMC/SQLERRD of the mapped error are not compared with z/OS; not measured there (#4702 Part 2).

### Q2. EXEC SQL keeps RETURN-CODE — ASSUMED
- The precompiled CALL preserves RETURN-CODE around the stub. Whether IBM's DSNHLI call resets it is not documented.
- **IBM.** The Db2 for z/OS Application Programming and SQL Guide describes the language interface module (DSNHLI)
  and the SQLCODE / SQLSTATE it returns; it does not say whether RETURN-CODE is preserved around the call. IBM is
  silent, so this is a declared oracle-vs-IBM difference risk, not a match: a program that reads RETURN-CODE after an
  EXEC SQL without setting it would differ. No burned program does.

### Q3. The Db2 unit of work — MATCHED for CICS tasks and for batch steps (#4269)
- **CICS.** The equivalence test runs each task's SQL in one Db2 transaction, as CICS's Db2 thread does: committed when
  the task ends, rolled back with the task's recoverable files by SYNCPOINT ROLLBACK or an abend (X3). The transaction
  is the harness's (`equivalence_cics.py`, a `TransactionTemplate` around the task); a deployment must give each task
  the same unit of work. Reached: CBSA XFRFUN's four ROLLBACK paths are proven.
- **CICS, SQL after a SYNCPOINT ROLLBACK (#4270).** IBM: SYNCPOINT ROLLBACK ends the unit of work and the task's next
  recoverable change starts a new one, committed when the task ends. The Java side rolls the task's Db2 connection back
  at the SYNCPOINT ROLLBACK and goes on in the same transaction, so the SQL that follows is committed with the task, as
  the COBOL side's Db2 commits it. Reached: CBSA INQACCCU's cursor failing inside CREACC's task (its SYNCPOINT
  ROLLBACK, then CREACC's CONTROL updates and INSERTs: cbsa-creacc, cbsa-bnk1cac). A recoverable FILE changed after a SYNCPOINT ROLLBACK is kept (#5089): the harness restarts the task's file transaction
  at the rollback (it backs out what came before and begins the next unit of work, committed when the task ends; an
  abend or a refusal still backs out only the current one), as the COBOL side keeps it. Reached: CBSA DELCUS deleting
  the CUSTOMER record after INQACCCU's rollback (cbsa-delcus: customer 3's NULL statement date, and the derived SQL
  faults at INQACCCU lines 246 and 466), equal in every output. A rollback after a SYNCPOINT stays refused by name.
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
- **Modelled (#4269).** `WHENEVER {SQLERROR | NOT FOUND | SQLWARNING} {CONTINUE | GO TO label}`: scoped by source
  order, tested against the SQLCA after each executable statement (SQLERROR, then NOT FOUND, then SQLWARNING, as IBM).
  `WHENEVER ... PERFORM` / `STOP` and a label that is not a paragraph are refused by name. A scroll cursor's
  `DECLARE` and its plain `FETCH` (GenApp LGIPDB01) run; no burned estate uses the forms below.
- **Modelled (#4269).** `EXECUTE IMMEDIATE 'INSERT ... VALUES ...'`: the string literal (an embedded quote doubled) is
  the statement text, run as written on the unit of work's connection, Db2 answering (-803, -204, ... land in the
  SQLCA; WHENEVER tests them). Proven on Db2 by the synthetic estate `tests/equivalence/db2/dynsql` (DYNDEMO; no
  burned estate issues dynamic SQL). **Assumption:** the connection returns no row count, so SQLERRD(3) is not set
  by the port while Db2 sets it to 1: a program that reads it after such a statement shows as a differing scenario,
  never as a silent pass. Refused by name: a host variable as the text, a parameter marker, a searched UPDATE / DELETE /
  MERGE and an INSERT ... SELECT (+100 when no row changes, which needs the count), DDL, COMMIT / ROLLBACK, a SELECT,
  and EXECUTE IMMEDIATE in a CICS program.
- **Modelled (#4269).** `PREPARE name FROM 'INSERT ... VALUES ...'` then `EXECUTE name` (no `USING`): the literal is kept
  at the PREPARE and run at each EXECUTE exactly as EXECUTE IMMEDIATE runs it. The PREPARE itself leaves SQLCODE 0
  and touches no row (the port and the oracle both run `VALUES 1`). Proven on the DYNDEMO estate (insert, then
  -803 on the second EXECUTE). **Assumptions:** Db2's -104 for text it cannot parse lands at the EXECUTE, not the
  PREPARE; an EXECUTE reached at run time before its PREPARE (-518) is not modelled (one placed before every PREPARE of
  the name in the source is refused). Refused by name: a name PREPAREd from two different literals, a host variable as
  the text, `INTO` / `ATTRIBUTES`, any text but INSERT ... VALUES, and a CICS program.
- **Modelled (#4269).** `EXECUTE name USING :H [:IND], ...` binding the parameter markers (`?`) of such a PREPAREd
  INSERT ... VALUES, one scalar host variable per marker (an indicator below zero is NULL). Proven on Db2 by DYNDEMO (the
  insert, a quote inside a bound value, -803 on a repeat, -407 for a NULL into a NOT NULL column). **Assumption:** the
  port writes each value into the text as a literal (character quoted with `'` doubled, number as its digits, NULL)
  where Db2 binds it, which gives the same row for an INSERT ... VALUES; a program that reads SQLERRD(3) shows as a
  differing scenario (as above). Refused by name: a marker in EXECUTE IMMEDIATE, a marker count that is not the host
  variable count (Db2 -313), `USING DESCRIPTOR`, a host structure or array, and a CICS program.
- **Refused (#4269), by form; burned estates using any of them: none** (pinned live by `test_no_burned_estate_program_issues_a_refused_dynamic_or_connection_sql_verb`
  in `tests/cobol_mainframe/test_sql_dynamic.py`, which fails when a burned program starts to use one; first run 2026-10-23).
  Each stops the det translator with `EXEC SQL <verb>: <form> (register Q4 ...)`:
  - `DESCRIBE` (SQLDA of a prepared statement or table): needs an SQLDA model; modelled when a burned program describes.
  - `CONNECT [TO loc | RESET]`: the port has one connection per run; a location switch needs a second oracle database.
  - `EXEC SQL CALL proc (...)`: a stored procedure needs a procedure fixture on the oracle (and result-set rules).
  - `PREPARE` of other text or from a host variable, `EXECUTE ... USING DESCRIPTOR`, `ALLOCATE` / `ASSOCIATE`: as above.
  - A `SET` that does not assign a host variable (`SET CURRENT SQLID`, ...).
  - Scroll `FETCH` orientations (`PRIOR`, `FIRST`, `LAST`, `CURRENT`, `BEFORE`, `AFTER`, `ABSOLUTE n`, `RELATIVE n`,
    with or without `INSENSITIVE` / `SENSITIVE`): the port steps a cursor forward one row, and the oracle has no scroll
    fixture. `FETCH` and `FETCH NEXT` run, as does a scroll cursor's `DECLARE` (GenApp LGIPDB01).
  - Multi-row (rowset) `FETCH ... ROWSET` / `FOR n ROWS` and `INSERT ... FOR n ROWS`, and host-variable arrays in SQL:
    each stops the det translator by name (`a multi-row FETCH / INSERT ... (register Q4)`).
    Pinned by `test_no_burned_estate_program_uses_a_scroll_fetch_or_multi_row_sql`
    (`tests/cobol_mainframe/test_sql_dynamic.py`): it fails when a burned program starts to use one.
  - A host variable in a savepoint statement (Q3) stops the precompiler and the det translator by name (and a
    savepoint statement in a CICS program the det translator), as does an undeclared host variable or a
    `WHERE CURRENT OF` a cursor the program does not declare. A positioned UPDATE / DELETE on a declared cursor runs (Q8).

### Q5. DSNTIAC stand-in (text unproven); DSNTIAR REFUSED
- **What.** Db2's message formatters (DSNTIAR formats an SQLCA into message text in a caller's buffer; DSNTIAC is its CICS
  interface; IBM Db2 for z/OS Application Programming and SQL Guide, paraphrased and not re-fetched for this entry). The
  text is Db2's message catalogue, which IBM documents by message number but not byte for byte, and the oracle
  (ggsql.c / equivalence_sql.py, Db2 for Linux) has no routine that produces z/OS's text.
  - **DSNTIAC (#5858): a stand-in, one model on both sides.** `cobolrt/le/Dsntiac.java` (the port) and
    `tests/equivalence/le/dsntiac.c` (linked into the GnuCOBOL oracle) hold the same message table and wrapping, so the
    two sides are compared on the CALL's contract: the message area is filled in whole lines of the stated line length
    (72 to 240), blank padded; RETURN-CODE is 0, 4 (more text than room), 8 (line length out of range), 12 (area holds no
    whole line) or 24 (SQLCA not a Db2 SQLCA). A SQLCODE the table does not hold (100, -204, -305, -530, -532, -803,
    -811, -904, -911, -913) is refused at run time ("not modelled"), never given invented text.
  - **DSNTIAR stays refused by name** (`CALL 'DSNTIAR'` or through a data item): "DSNTIAR: Db2's message text is not
    modelled".
- **Assumption (unproven).** The wording of each message line, and the DSNT415I / 416I / 418I trailer lines, are written
  from the public message titles, not captured from z/OS. A scenario that prints them proves the port equals the stand-in,
  not that z/OS prints the same bytes. Residual risk: a program that parses the text, not the return code.
- **Reached.** COTRTLIC's `9999-FORMAT-DB2-MESSAGE` (CALL LIT-DSNTIAC, #4736), on the Db2-error path: the injected SQL
  faults of `carddemo-cotrtlic` reach it and both sides agree.

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
- **IBM.** The Db2 for z/OS Command Reference (BIND PACKAGE, DATE option) sets the date format of output host
  variables (ISO, EUR, USA, JIS or LOCAL; default the installation's, ISO as IBM ships it); the SQL Reference defines
  the ISO string form `yyyy-mm-dd`.
- **Declared difference.** The harness database's USA default for `CHAR(date)` in SQL text, and the removed
  placement and audit clauses, are a declared oracle-vs-IBM difference; none changes a proven result.

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
- **IBM.** Db2 13 for z/OS Codes, SQLCODE -508 (SQLSTATE 24504): "The cursor must be positioned on the row that is to be
  updated or deleted" (UPDATE or DELETE WHERE CURRENT OF). The COBOL side is the statement as written; the Java side
  reproduces the same SQLCODE.
- **Declared difference.** The Java side's `RID_BIT` row addressing is not a mechanism IBM documents (the existing `RID_BIT` note above
  stands); it is our implementation choice, and only the SQLCODEs are compared.

### Q9. More host variables than columns — MATCHED
- GenApp's LGUPDB01 FETCHes six host variables from a five-column cursor (a GenApp defect). IBM sets nothing and leaves the
  sixth as it was; both sides set SQLWARN3 and leave it as it was (the COBOL stub had reported an error, the Java side a
  NULL).
- **IBM.** Db2 13 for z/OS FETCH (SQL Reference): "There is no warning if there are more targets than the number of
  result columns." SQLWARN3 is 'W' only "if the number of result columns is larger than the number of host variables"
  (Db2 10 SQL Reference, Description of SQLCA fields). The extra variable is left unchanged, which both sides do.
- **Declared difference.** Both sides set SQLWARN3 (and SQLWARN0) 'W' for the extra variable, which IBM does not
  (ggsql.c, `DetSql.into`). The oracle and port agree, so no proof differs; LGUPDB01 does not test SQLWARN3. Aligning
  both to IBM moves the DetSql overlay copies under tests/cics_crucible/ports and needs re-proofs: a separate slice.

### Q10. A statement the driver fails with no Db2 SQLCODE — REFUSED (#4270)
- **What.** A host variable Db2 cannot take (GenApp LGAPDB01's INSERT COMMERCIAL with a blank CA-LASTCHANGED as its
  REQUESTDATE, reached when the SELECT LASTCHANGED before it is faulted) fails in the client: Db2's CLI gives its own
  native code -99999 (SQLSTATE 22007), IBM's JDBC driver its own -4220. What Db2 for z/OS answers is not known here,
  so the COBOL stub stops the task by name ("the CLI failed it in the client") instead of passing -99999 on as an
  SQLCODE: an enumerated fault task (M2) that reaches it is not judged; a declared scenario stops the case.

## IMS DL/I (`equivalence_ims.py`, `ggdli.c`, `DetDli`)

### I1. DL/I database calls through a DB PCB — the stated database model
- **What is modelled** (#4893). A batch DL/I program: IMS enters it at ENTRY 'DLITCBL' with the PSB's DB PCBs (CMPAT=NO,
  a DLI region), and it issues `CALL 'CBLTDLI' USING function pcb io-area [ssa ...]`. The COBOL side runs against
  `tests/equivalence/ims/ggdli.c`, the det port against `cobolrt/dli/DetDli.java`: one rule set, one set of refusals.
  The calls are GU, GHU, GN, GHN, GNP, GHNP, ISRT, REPL and DLET (IBM IMS 15.3 Application Programming APIs, "DL/I calls
  for database management"; the application side is in IMS 15.3 Application Programming, ibm.com/docs/en/SSEPH2_15.3.0/pdf/IMS_15.3_Application_Programming.pdf).
- **The database is stated, not connected.** The case names its DBD and PSB sources, which the engine's own macro
  reader parses (`gitgalaxy/core/ims_gen.py`), and a seed: the corpus's own HD unload (I6), or segments the case writes.
  Both sides read the same `dbd.cfg` / `psb.cfg` / `seed.<DBD>`, and each writes the database it ended with. The
  harness compares those segment by segment, every field of the segment's copybook layout (`equivalence_ims.diff_db`).
  The database is a hierarchy in hierarchic sequence: each parent's children by segment type in DBD order, and twins in
  sequence-field order (I2). HIDAM, PHIDAM, HISAM and SHISAM are read alike. The HIDAM index is not a database here:
  it only orders the roots by key, which the hierarchy already does.
- **Status codes** (IMS 15.3 Messages and Codes, Volume 4: IMS Component Codes, "Database calls for DL/I status
  codes", ibm.com/docs/en/ims/15.3.0?topic=codes-database-calls-dli-status):
  - blank: success.
  - GA: an unqualified GN / GNP moved up a level. GK: it returned a segment of another type at the same level.
  - GE: segment not found, or ISRT's parent not found. GB: GN reached the end of the database.
  - GP: GNP with no parentage. II: ISRT of a segment whose key its twins already hold.
  - DJ: REPL / DLET without a get-hold call just before. DA: REPL / DLET whose I/O area changed the sequence field.
  - AC: SSA naming a segment the DBD lacks, or SSAs out of hierarchic order. AJ: invalid SSA (qualification start,
    operator, end). AK: invalid field name. AD: invalid function. AM: function the PCB's PROCOPT does not allow.

  Any other condition is refused (I5).
- **RETURN-CODE after the call.** Each call returns 0: the C model returns 0 (GnuCOBOL stores it in RETURN-CODE), and
  the det port stores 0. IBM is silent on what the DL/I language interface leaves in register 15 for a COBOL
  CALL (the IMS 15.3 Application Programming pages name only the status code in the PCB). A program that reads RETURN-CODE after a DL/I call, or ends without setting it, relies on this assumption:
  PAUDBUNL ends RETURN-CODE 0 after its last GN (GB).

### I2. Sequence-field order and SSA comparison — the stored bytes, in the data page
- **Order.** Twins sit in the order of their sequence field's bytes, compared unsigned, on both sides. That is
  IMS's own order for the bytes it holds. The corpus is evidence: CardDemo's unload of DBPAUTP0 (HIDAM, ACCNTID TYPE=P)
  holds a root whose key is EBCDIC spaces (X'404040404040') after every valid packed key, which is a logical
  comparison, not a packed one. A seed not in that order is refused: the oracle's byte order would not be the
  estate's.
- **DIFFERS for text keys.** The harness's data page is ASCII-family (Latin-1), so a C key holding letters and digits
  sorts in ASCII order on both sides, where z/OS sorts it in EBCDIC order (digits after letters). This is the
  declared collation difference of indexed files (`COLLATION` in equivalence.py), here for twin order and for the GN /
  GNP that walks it. No proven case reaches it.
- **Qualification** (IMS Application Programming APIs, "SSA: relational operators"). The operators are EQ, GT, LT,
  GE, LE and NE, and their symbolic forms (`=`, `>`, `<`, `>=` / `=>`, `<=` / `=<`, `¬=` / `=¬`, each with a blank to
  fill two bytes). A C or X field compares bytes. A P field compares arithmetically in IMS; the model compares bytes
  only when both operands are valid packed numbers with the same positive sign (C or F), where the two comparisons
  agree, and refuses otherwise by name. Any other field type in a qualification (Z, H, F, ...) is refused.

### I3. Current position and parentage after each call
- **What is modelled** (IMS 15.3 Application Programming, Chapter 15 "Current position in the database after each call", p. 241-247, ibm.com/docs/en/SSEPH2_15.3.0/pdf/IMS_15.3_Application_Programming.pdf).
  - A successful GU, GN or GNP sets position on the segment it returned. GU and GN also set parentage there; GNP
    leaves parentage alone. An unqualified GN continues from position in hierarchic sequence, and GNP stays under
    the parent.
  - GB sets position to the start of the database, so the next GN returns the first root.
  - GNP's GE, when it walked the parent's dependents to their end (unqualified SSAs, or none), leaves parentage, and
    leaves position past the parent's last dependent. PAUDBUNL relies on this: its next GN of a root continues from
    there.
  - ISRT sets position on the segment inserted. DLET sets position just before where the deleted segment was, so the
    next GN goes on past it. REPL leaves position alone. A hold lasts until the next call on that PCB.
- **Left open, so refused.** IBM describes position after other unsuccessful calls in terms of IMS's own search:
  after a GE from GU or ISRT, after II, or after a qualified GN / GNP that finds nothing, where the search stopped
  depends on the access path. The model marks position (and, after GU, GN or ISRT, parentage) as open. A later
  call that needs it (GN, GNP, an ISRT located by position) stops by name. The same applies after ISRT (parentage),
  and on another PCB whose position or parentage a DLET removed.
- **Not settled.** Whether a qualified GN that finds nothing answers GE or GB depends on IMS's sequence-field search
  (it may stop early at a key past the qualification): refused by name.

### I4. The DB PCB mask — layout from IBM, the initial contents and an unsuccessful call's feedback assumed
- **Layout** (IMS 15.3 Application Programming, "Specifying the DB PCB mask", Table 35, p. 212, ibm.com/docs/en/SSEPH2_15.3.0/pdf/IMS_15.3_Application_Programming.pdf):
  - DBD name (8 bytes), segment level (2 characters), status code (2), processing options (4), reserved (fullword)
  - segment name (8), key feedback length (fullword), number of sensitive segments (fullword), key feedback area
- **No IBM copybook ships.** Neither the PCB mask macro nor an IBM copybook does. The program's own mask, CardDemo's
  PAUTBPCB, is the estate's copybook, and the harness builds the area IMS would pass from the PSB (36 bytes and its
  KEYLEN).
- **Assumed.** IBM is silent on the mask's contents at entry (beyond the data-availability status code) and on the feedback after GE or II beyond "the last segment it encounters that satisfied your call" (Table 35, note 2); the rest is ours.
  - At entry the mask holds the DBD name, level `00`, status blank, the PCB's PROCOPT, reserved 0, a blank segment
    name, key feedback length 0, the number of sensitive segments, and X'00' through the key feedback area. Every byte
    past it that the program's mask names is X'00' too: z/OS has the PCB control block there, which no program should
    read.
  - A successful get or ISRT sets the level, segment name and concatenated key of the segment, and the key feedback
    length. Bytes past that length keep what they held.
  - A GE from GU or ISRT gives the deepest segment along the SSAs' path that IMS could satisfy (level `00`, a blank
    name and length 0 when none could). GNP's GE gives its parent, and II gives the parent of the segment ISRT tried
    to insert. GB, REPL and DLET leave level, name and key feedback as they were.

### I5. DL/I beyond the modelled calls — REFUSED
- **Refused by the det translator.**
  - EXEC DLI SCHD PSB and TERM under CICS are translated (#5278): `DetDli.schedule` / `terminate` answer DIBSTAT
    (blank; TC for a PSB already scheduled, given NODHABEND). The CICS harness runs them against `ggdli.c` (below).
  - EXEC DLI GU, GN and GNP under CICS are translated (#5278) with PCB(n), SEGMENT, WHERE (one field, operator, data
    area) and INTO: `DetDli.get` builds the SSAs and reuses the modelled call, answering DIBSTAT (GE, GB, AC, AK as
    IBM does; a refusal by name with no PSB scheduled or a PCB number the PSB lacks). ASSUMPTION: a PCB with
    PROCOPT A / R / D is read with hold (GHU / GHN / GHNP), as IBM holds for update; no IBM text is cited for it.
    The CICS harness runs them against `ggdli.c` (below).
  - The oracle side (#5278): `equivalence_cics.py` rewrites each EXEC DLI to a CALL of `ggdli.c`'s `GGDLISCHD`,
    `GGDLIX` and `GGDLITERM` (the batch CBLTDLI core underneath, PCB by number, DIBSTAT = the PCB mask status), stages
    the case's `ims` DBD / PSB / seed in the scenario directory, and compares a `DLI-DBS` event (each database's bytes at
    exit) beside the CICS events, which carry the control flow DIBSTAT drives. Up to 3 SEGMENTs, a WHERE value a data
    name, INTO / FROM a data name. Not logged per command: the compare is the final database plus the program's own
    output. The oracle is GnuCOBOL plus our model of DL/I, not IMS.
  - EXEC DLI in a BMP (#5857) is translated when the program is entered `PROCEDURE DIVISION USING io-pcb db-pcb ...`
    (IMS passes the I/O PCB first, PSB CMPAT=YES; PCB(n) counts it, so the first database PCB is PCB(2) and PCB(1) is
    refused by name): GN, GNP and the writes as under CICS, the DIB (DIBSTAT only), and CHKP ID(area) (`DetDli.checkpoint`,
    DIBSTAT blank, ID of 8 bytes). ASSUMPTION: a basic CHKP loses every database position, so the next GN starts at the
    beginning; no IBM text is cited for it. The oracle side is linked (#5857): `equivalence_ims.py` accepts CMPAT=YES for a BMP entered USING its I/O PCB and
    DB PCBs, `ggdli.c` binds them (`GGDLIBMP`, refusing PCB(1) and SCHD/TERM) and models CHKP (`GGDLICHKP`: every
    position lost, the same uncited ASSUMPTION as the Java side), and `rewrite_bmp` lowers GN/GNP/DLET/CHKP ID(area).
  - CALL 'CBLTDLI' in a BMP (#5233) is the same lane: a program with `PROCEDURE DIVISION USING io-pcb db-pcb ...` whose
    `ENTRY 'DLITCBL'` lists exactly the DB PCBs (PAUDBLOD: IMS enters a BMP at the header and passes the I/O PCB first,
    CMPAT=YES, so the ENTRY list is the header's minus its first) is read as a BMP on both sides (`stmt.Procedure.division_using`,
    `dli.entry_pcbs` / `bmp_pcbs`, `equivalence_ims.bmp_using`). An ENTRY with no header USING, or whose list is not that, stays the
    batch DLITCBL path (PAUDBUNL, DBUNLDGS). The I/O PCB passed to CBLTDLI (an IMS TM message call) is refused by name. Run as
    `carddemo-paudblod` (INFILE1 / INFILE2 generated from the program's own record layouts: they are not in the corpus), a
    database loaded by ISRT root, GU root, ISRT child; no DIB is built for a program with no EXEC DLI.
  - Every other EXEC DLI command (XRST, ROLB, GHU ...) stays a hole by name, as do the get clauses not modelled
    (FIELDLENGTH, KEYS, a multi-field WHERE, SEGMENT-less WHERE), CHKP with any option but ID, and EXEC DLI outside
    CICS in a program that is not such a BMP.
    CardDemo COPAUA0C (GU, ISRT, REPL under CICS; its MQ calls are modelled, W6) is translated and run as
    `carddemo-copaua0c` (17 scenarios, #5278, since extended); COPAUS0C and COPAUS1C are run as `carddemo-copaus0c` and
    `carddemo-copaus1c` (#5233). Unit-of-work calls: the burned IMS programs issue only SCHD, TERM (CICS) and CHKP (CBPAUP0C), all
    translated and run; none issues XRST, ROLB or SYNC (pinned by `test_dli_uow_burned_5233.py`), so those stay refused by name. CBPAUP0C (the BMP) is run as
    `carddemo-cbpaup0c` (#5857) on the corpus's own DBPAUTP0 unload (22 roots, 202 children), a PRM-INFO card of 13
    expiry days at 2023/11/01 and a checkpoint every 2 summaries: 41 details deleted, CHKP taken, 183 of 224 segments
    left, equal on both sides. With 5 expiry days the first summary's DLET fails DJ (its preceding call was the GNP
    that answered GE, not a successful get) and the step abends, RC 16, on both sides. ASSUMPTION (no IBM text cited): a BMP whose
    LINKAGE masks are PIC X (CBPAUP0C's) never names the mask, so `DetDli.enterBmp` gives the PCB the runtime's own
    36-byte mask; the oracle's driver area is larger, so only the program's first mask byte differs between sides.
  - ASSUMPTION (#5278, no IBM text cited): under CICS, EXEC DLI numbers the DB PCBs from 1 with no I/O PCB first, so a
    PSB's CMPAT=YES changes nothing there; the harness takes it for a CICS case (`equivalence_ims.psb(cics=True)`). Owner
    to confirm.
  - DL/I status faults under CICS (#5233): a scenario's `dli_faults` (`{op, nth, status}`; op SCHD or a get / write
    call, not CHKP; nth a count or `"*"`) is written as the plan both stubs read (`ggdli.c` `planned_dli`,
    `DetDli.planned`). A planned call is not performed: DIBSTAT answers the status, and each fired fault is logged and
    compared (a fault that fires on one side only fails). SCHD answers TC only, the one status the model derives.
  - Boolean qualification (#5233): one SSA may join qualification statements, `SEG(F1 op v1 & F2 op v2 ...)`, with AND
    (`&` or `*`) and OR (`+` or `|`). Per IBM, statements joined by AND form a set and the SSA holds when any set does
    (AND binds tighter than OR). Every statement is evaluated, so a refusal (a P field with a sign mismatch, a field type other
    than C / X / P) does not depend on the data. A character after a statement that is neither `)` nor an operator is AJ,
    an unknown field in any statement AK. No burned program uses it: the proof is the fixture `DLIBOOL` on both runtimes
    (`tests/equivalence/ims/fixture`, expected output written from IBM's documentation before either runtime ran it).
  - Command codes (#5233): an SSA may carry `SEG*codes(` or `SEG*codes ` (a blank for an unqualified SSA). Modelled: `-`
    (null, ignored anywhere), `F` and `L`. On a GU / GHU, `F` is the default start and changes nothing; `L` on the last,
    unqualified SSA answers the last twin of that type under the parent the path found. On an ISRT both are ignored
    (every modelled sequence field is unique). ASSUMPTION (no IBM text quoted; written from memory of IBM's description):
    `F` / `L` have no effect on an ISRT with a unique sequence field. Refused by name on both runtimes, with the code in
    the message: `F` on a GN / GNP, `L` on a GN / GNP, on a qualified SSA or on a path SSA, and every other code
    (`N 1-9` and any other letter), even later in a list. `P` is modelled on a GU / GHU only (below); on any
    other call, or twice in one call, it is refused by name. No burned program uses one: the proof is the fixture
    `DLICMD` on both runtimes (`tests/equivalence/ims/fixture`, expected output written from IBM's documentation).
  - Command code `Q` (#5233): enqueue. Modelled on a get (GU / GHU / GN / GHN / GNP / GHNP), on an unqualified or qualified SSA and
    beside the other modelled codes, as no effect: the oracle runs one program, so no other program holds the segment
    and none waits. ASSUMPTION (no IBM text quoted; written from memory of IBM's description): `Q` does not change a status
    or position, and the DEQ call that releases an enqueue is not modelled (DEQ stays refused as any other function). Refused by
    name on both runtimes on an ISRT (REPL / DLET take no SSA). `N` and the rest
    stay refused by name. No burned program uses one: the proof is `DLICMD` (Q40-Q45) on both runtimes.
  - Command codes `U` and `V` (#5233): the current position as qualification, on a get (GU / GHU / GN / GHN / GNP / GHNP). `U`
    on an SSA requires the segment found at that SSA's level to be the one on the current position (the position's
    ancestor-or-self of that type); `V` does so for that SSA's level and every level above it (the last `V` in the call
    decides how far). Both hold beside a qualification and the other modelled codes. ASSUMPTION (no IBM text quoted; written
    from memory of IBM's description): with no established position (none yet, or left open by an earlier failed call), or
    when the position is not at or below the SSA's level, the call is refused by name rather than answered with a status;
    a GN that finds nothing under U / V answers as without them. Refused by name on both runtimes on an ISRT and beside
    `C` (REPL / DLET take no SSA). No burned program uses one: the proof is `DLICMD` (Q46-Q55) on both runtimes.
  - Command code `N` (#5233): no replace, with `D` on a get-hold (GHU / GHN / GHNP). A REPL straight after such a get replaces
    each segment the path call returned from its slice of the I/O area (the concatenation `D` hands back), except the segments
    whose SSA carried `N`. A sequence field changed in a replaced segment answers DA and nothing is replaced; an `N` segment's
    slice is not compared. A DLET after a path call is refused by name. Refused by name on both runtimes: `N` without `D`, and
    `N` on any call but a get-hold. ASSUMPTION (no IBM text quoted; written from memory of IBM's description): a REPL after
    a D path call with no `N` replaces every segment returned; the other REPL path forms stay refused. The Java runtime refuses an I/O area shorter than the concatenation; the C twin cannot see the area's size. No
    burned program uses one: the proof is `DLICMD` (Q56-Q70) on both runtimes.
  - Command code `P` (#5233): on a GU / GHU it sets parentage at the level of its SSA (the ancestor of the retrieved
    segment of that SSA's type, or the segment itself) instead of at the lowest segment retrieved, so a following GNP
    walks the dependents of that segment. `P` on the last SSA is the default. Position and the I/O area are those of
    the retrieved segment. ASSUMPTION (no IBM text quoted; written from memory of IBM's description): `P` on a GN /
    GNP (where parentage is already set) and on an ISRT is not modelled; it is refused, not guessed. The proof is
    `DLICMD` (Q11-Q24), expected output written from the description before either runtime ran it.
  - Command code `C` (#5233): `SEG*C(key)` names a segment by its concatenated key, the sequence-field values from the root
    down to that segment (the sum of those key lengths, no field name or operator). Modelled on a GU / GHU as the only SSA:
    both runtimes read it as one SSA per level qualified EQ on that level's key, so position, parentage, feedback and GE are
    those of the ordinary path call. Refused by name: C on a GN / GNP / ISRT, C beside another SSA, C with L; a C with no
    parentheses is AJ. ASSUMPTION (no IBM text quoted; written from memory of IBM's description): C beside other SSAs and
    a key that does not end at its `)` (IMS answers a status for a short key) are not modelled. The proof is `DLICMD`
    (Q25-Q29), expected output written from the description before either runtime ran it.
  - Command code `D` (#5233): a path call. On a GU / GHU / GN / GHN / GNP / GHNP, each D-coded SSA other than the last
    returns its segment (the found segment's ancestor of that type), in hierarchic order, then the found segment itself, one
    after another in the I/O area (the segments are fixed length, so no LL fields). D on the last SSA adds nothing. PCB
    feedback, position, parentage and status are those of the last segment found. The I/O area must hold the whole
    concatenation: the Java runtime refuses a shorter one, the C twin cannot see the area's size, so the program's area is
    the program's job there. Refused by name: D on a REPL / DLET (the path replace is modelled only as a REPL after a D get-hold, with N), D beside C. ASSUMPTION (no IBM text quoted; written from memory of IBM's description): D on a GN / GNP
    returns the ancestors on the found segment's own path, the same rule as a GU. The proof is `DLICMD` (Q30-Q39), expected output written from the description before either runtime ran it.
  - Command code `D` on an ISRT (#5233): the path insert. The I/O area holds each D-coded segment and then the last segment, fixed
    length, in hierarchic order, and the SSAs start at the root. A level that exists is kept (a D-coded level's slice is not
    compared; a non-coded level is found by its SSA); a missing D-coded level is created from its slice, if it satisfies its own
    SSA; a missing non-coded level answers GE; the last segment answers II if its twin exists, otherwise it is inserted. Feedback and
    position are those of the last segment. The Java runtime refuses an I/O area shorter than the segments; the C twin cannot see
    the area's size. Refused by name: N on an ISRT (N is for a get-hold with D), a path ISRT not starting at the root. ASSUMPTION (no IBM
    text quoted; written from memory of IBM's description): an existing D-coded segment is kept and its slice is not compared. No
    burned program uses one: the proof is `DLICMD` (Q71-Q82) on both runtimes, plus a Java-only test of the short area.
  - ASSUMPTION (#5233, no IBM text cited): a qualified GNP that finds nothing answers GE with the parent's feedback and
    parentage kept; position is open (I3), so the next GN / GNP is refused by name, as after a GU's GE. Whether a
    qualified GN answers GE or GB stays unsettled (I3), and is still refused.
  - GSAM PCB in load mode (#5233, rule RT-DLI-GSAM; case `carddemo-dbunldgs`): a database with ACCESS=(GSAM,..) and a fixed
    RECORD=(n) is a sequential output file, and a TYPE=GSAM PCB with PROCOPT LS ISRTs into it with no SSA, each ISRT
    appending one record of n bytes from the I/O area; the harness compares the records in order, by field when the case
    names a copybook (`ims.gsam`). ASSUMPTION (no IBM text cited): any function but ISRT on a GSAM PCB answers AM, and the
    PCB mask's segment level is blank (a GSAM PCB has no segment). Refused by name on both runtimes: an ISRT with an SSA,
    an I/O area shorter than the record, and two GSAM PCBs on one database. Burned estate (pinned by
    `test_gsam_burned_5233.py`): only DBUNLDGS / DLIGSAMP.PSB use GSAM, both PCBs PROCOPT=LS and ISRT-only; reading a
    GSAM file (PROCOPT G) is needed by no burned program and stays refused by name in the harness (`equivalence_ims.psb`).
  - Load mode on a DB PCB (#5233, rule RT-DLI-ISRT; proof `test_det_dli.py::test_load_mode_*`): a PCB with PROCOPT L or LS alone
    loads an empty database; ISRT is the only call that works and every other function answers AM. An ISRT names its segment
    type and loads it as the last child of the last loaded segment of the parent type (an unqualified parent SSA is not
    needed). Status codes (IBM's load statuses): LB for a key equal to the last twin's, LC for a key below it, LD when no
    parent of the type is loaded, LE for a type that comes before one already under the parent. ASSUMPTION (no IBM text
    cited): the precedence is LE, then LB / LC, and a load-mode ISRT's feedback and position are those of an ordinary ISRT.
    Refused by name on both runtimes: an ISRT with SSAs before the last and a load into a database that already holds
    segments; refused by the harness: PROCOPT L with another option, a load PCB beside another PCB on the same DBD, load mode
    under CICS. Needed by no burned program.
  - A case's `ims.seed.<DBD>.skip` lists unload record numbers left out of the seed (the corpus unload of DBPAUTP0 ends
    with a root whose packed key is blank, which a qualified GU refuses by design).
  - CALL 'CBLTDLI' is refused in a program IMS does not enter at ENTRY 'DLITCBL' or as a BMP (an MPP or CICS program), and with the I/O PCB.
  - Also refused: the parameter-count form (a binary count first), a PCB the entry was not passed, any ON EXCEPTION
    phrase, and CALL 'AIBTDLI'.
  - CALL 'CEETDLI' (#5233, LE's interface, the same USING list as CBLTDLI) is translated at ENTRY 'DLITCBL' on both runtimes
    (`ggdli.c` `CEETDLI` and `DetDli.call`); in a BMP entered USING its I/O PCB it stays a hole by name. No burned program calls it:
    the proof is the fixtures `DLILVL`, `DLICMD` and `DLIBOOL` with CBLTDLI renamed, each equal to the unrenamed run.
  - IMS TM / MFS (#5233): message calls on the I/O PCB (GU / GN / ISRT of a message), CHNG / SETO / PURG / CMD / INQY, MPP
    entry and MFS screens are needed by no burned program (PAUDBLOD is the only one handed an I/O PCB, and it never calls
    on it); they stay refused by name and nothing is modelled. `test_paudblod_bmp_5233.py` pins that census over the
    CardDemo IMS programs, so a burned program that starts to need them fails there first. The other burned estates have no DL/I.
  - CALL 'CBLTDLI' from a CICS program (#5233): no burned CICS program makes it (COPAUA0C / COPAUS0C / COPAUS1C use EXEC DLI;
    the only CBLTDLI callers are the batch / BMP PAUDBLOD, DBUNLDGS, PAUDBUNL). The CICS harness refuses a CICS source that CALLs
    CBLTDLI, AIBTDLI or CEETDLI by name (`equivalence_cics.refuse_dli_call_interface`), and `test_cblt_dli_cics_5233.py` pins the
    census over the burned estates. The UIB-addressed PCB list a CICS CBLTDLI program reads is not modelled.
- **Needed by no burned program** (#5233, `test_dli_unburned_census_5233.py` pins the census over the six burned estates): CALL 'AIBTDLI',
  the FLD / POS / INQY calls, XDFLD / PROCSEQ secondary indexes, logical relationships (PAIR, LPARENT, a non-index LCHILD),
  HDAM / PHDAM / DEDB access, the `#` (independent AND) operator and the DEDB subset-pointer command codes (M R S W Z 1-9; the
  census scans burned programs that issue DL/I, and the refusals are run on both runtimes in `test_det_dli.py`). All stay refused by name below. CardDemo's DBPAUTP0 / DBPAUTX0 are a HIDAM primary index, not a
  secondary one. A burned program that starts to need one fails the census first.
- **Refused by the harness** (`equivalence_ims.Unsupported`, "not runnable faithfully"):
  - HDAM and PHDAM: the root sequence is the randomizer's.
  - INDEX and LOGICAL databases, and a GSAM database with variable-length records or no fixed RECORD=(n).
  - Logical relationships, variable-length segments, a non-unique or missing sequence field.
  - CMPAT=YES outside a BMP (IMS TM passes an I/O PCB first; taken under CICS, see the ASSUMPTION), and an I/O or alternate PCB, a GSAM PCB with a PROCOPT but LS (reading a GSAM file, PROCOPT G), and a PSB with
    two GSAM PCBs on one database.
  - XDFLD (a secondary index; #5233) and any LCHILD but a primary index (POINTER=INDX), PROCSEQ (a secondary index), PROCOPT L with another option (and a load PCB beside another PCB on its DBD), a segment-level PROCOPT, and a PCB not sensitive to every
    segment.
  - An ENTRY 'DLITCBL' that does not name one area per PCB.
- **Refused by both runtimes at run time** ("CBLTDLI: ... is not modelled"; exit 98 on the COBOL side):
  - Any DL/I call but the nine modelled ones (CHKP, XRST, ROLB, SYNC, LOG, STAT, GSCD, FLD, POS, INQY, PCB, TERM and
    the message calls).
  - An SSA with command codes, and the `#` (independent AND) operator, which belongs to secondary indexes.
  - More than 16 qualification statements in one SSA.
  - SSAs that leave out a level (a GU or path ISRT not starting at the root, or a gap between two SSAs).
  - REPL / DLET with SSAs, an ISRT with no SSA or a qualified last SSA, and get-hold under PROCOPT O.
  - The open-position cases of I3 and the comparisons of I2.

  An unknown function code is AD, as IBM answers it.

### I6. The corpus's HD unload read as a seed — its record layout observed, checked against its trailer
- **What.** CardDemo ships its pending-authorization database as an HD reorganization unload
  (`data/EBCDIC/AWS.M2.CARDDEMO.IMSDATA.DBPAUTP0.dat`). The harness reads it as the case's seed:
  - Each record starts with a halfword length and a halfword of zeros, then the segment level and flag bytes.
  - The segment's length (halfword) is at offset 8 and its name (8 bytes, EBCDIC) at offset 10.
  - Its data is the `length` bytes before the record's last byte.
  - The first record is the header and the last the trailer.
  - Each segment is laid out by its copybook into the case's data page: text through CCSID 037, COMP / COMP-3 bytes as
    they are.
- **Assumed, and checked.** IBM documents the utility, not this record layout byte by byte. The layout above is the
  one observed. It is checked twice. The trailer's per-segment counts (a fullword 32 bytes after each segment name)
  must equal the segments read, 22 roots and 202 children. And every root's key and every child's two packed fields
  must decode as valid packed numbers, except one root whose key is spaces (I2). A file that does not match is refused,
  never seeded.

- **IBM (document).** The utility is documented in IMS Database Utilities (IMS 15 Database Utilities, the HD
  Reorganization Unload utility DFSURGU0 and its reload counterpart DFSURGL0) at
  https://www.ibm.com/docs/en/ims/15.4.0?topic=utilities-hd-reorganization-unload-utility-dfsurgu0. The wording is
  paraphrased, not verbatim.
- **Declared difference.** IBM documents what the utility does, not the byte layout of its output file, so the layout
  here is an observation of one corpus's file, not an IBM-quoted format. The oracle does not run DFSURGU0 or DFSURGL0;
  it reads the file as a seed. The two checks above are what stands in for a quoted layout, and a file that fails
  either is refused.

## IBM MQ (ggmq.c)

### W1. The MQ copybooks — GitGalaxy-written stand-ins of the version-1 structures and the modelled constants only
- **What.** IBM's MQ copybooks (SCSQCOBC) are in no estate and are never shipped. The det translator ships
  `det/copy/CMQV.cpy`, `CMQODV.cpy`, `CMQMDV.cpy`, `CMQGMOV.cpy`, `CMQPMOV.cpy` and `CMQTML.cpy`, written from IBM's
  public documentation (each field's name, type, order and initial value), used only where the estate holds none of
  its own, and shipped only together with the model behind them (owner, 2026-10-11): the det runtime's
  `cobolrt/mq/QueueManager.java` and the oracle's `tests/equivalence/mq/ggmq.c`.
- **What they declare.** The version-1 structure of each: MQOD (168 bytes), MQMD (324), MQGMO (72), MQPMO (128), MQTM
  (684) -- IBM's MQ*_LENGTH_1 -- with IBM's initial values (MQMD Encoding MQENC_NATIVE = 785, z/OS). CMQV declares only
  the constants the modelled calls give a meaning to (MQCC_*, the reason codes the models return, the MQOO_ / MQGMO_ /
  MQPMO_ options modelled, MQCO_NONE, MQMI_NONE, MQCI_NONE, MQFMT_NONE / STRING, MQCCSI_Q_MGR, MQMT_*, MQOT_Q,
  MQPER_*). A program naming any other constant, or a later structure version's field, does not compile: refused,
  never guessed. Both models refuse a structure whose StrucId / Version is not the version-1 one.
- **Assumed.** That the layouts and values are IBM's. `tests/cobol_mainframe/test_det_mq.py` checks each stand-in's
  length against IBM's MQ*_LENGTH_1 and its VALUE clauses against IBM's initial-value tables, and CMQV's values
  against IBM's constants.
- **IBM references.** MQMD https://www.ibm.com/docs/en/ibm-mq/9.3?topic=mqi-mqmd-message-descriptor ; MQOD https://www.ibm.com/docs/en/ibm-mq/9.3?topic=mqi-mqod-object-descriptor ;
  MQGMO https://www.ibm.com/docs/en/ibm-mq/9.3?topic=mqi-mqgmo-get-message-options ; MQPMO https://www.ibm.com/docs/en/ibm-mq/9.3?topic=mqi-mqpmo-put-message-options ;
  MQTM https://www.ibm.com/docs/en/ibm-mq/9.3?topic=mqi-mqtm-trigger-message ; constants https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-constants

### W2. MQGET WAIT — no other producer during the task: a wait on an empty queue ends with MQRC_NO_MSG_AVAILABLE at once
- **IBM.** With MQGMO_WAIT the call waits up to WaitInterval for a suitable message, then fails with
  MQRC_NO_MSG_AVAILABLE (2033).
- **Assumed.** The case's queues are the whole world of the task: nothing else puts while it runs, so a wait that
  finds no message ends the same way it would after the interval, and the models answer 2033 at once (the clock does
  not move). A wait with MQWI_UNLIMITED on an empty queue would never end: refused by name, as is a negative
  WaitInterval other than MQWI_UNLIMITED (IBM: MQRC_WAIT_INTERVAL_ERROR, not modelled).
- **Not modelled.** A concurrent producer, MQGMO_SET_SIGNAL, and triggering itself (CKTI starting the transaction): a
  case states the trigger message the task is started with instead (W8's neighbour: `start_data`, the MQTM).
- **IBM (document).** IBM MQ Application Programming Reference, MQGET and MQGMO (WaitInterval, MQGMO_WAIT,
  MQWI_UNLIMITED), and the MQRC_NO_MSG_AVAILABLE (2033) and MQRC_WAIT_INTERVAL_ERROR reason codes
  (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-mqget-get-message). The wording is paraphrased, not verbatim.
- **Declared difference.** IBM waits the full WaitInterval before 2033; the models answer at once because no
  producer can put meanwhile.

### W3. Queues — local queues the case states, delivered by priority then first in first out
- **What.** A case's `"mq"` section states the queue manager (its name and CCSID) and its local queues with their
  default priority and persistence and the messages each holds at the task's start (tests/tools/equivalence_mq.py),
  given alike to both models as `mq.cfg`. Any other name is MQRC_UNKNOWN_OBJECT_NAME (2085). A message's MQMD fields
  not stated are IBM's initial values, resolved as a put resolves them.
- **Assumed.** MSGDLVSQ(PRIORITY), IBM's default: a get takes the highest priority first, first in first out within a
  priority. DEFPRTY(0) and DEFPSIST(NO), the IBM defaults, unless the case states otherwise.
- **Not modelled (refused by name).** Remote, alias, model and dynamic queues, a queue on another queue manager
  (ObjectQMgrName), object types other than MQOT_Q, MQOO_BROWSE / INQUIRE / SET / SET_*_CONTEXT /
  ALTERNATE_USER_AUTHORITY, a second input handle beside an MQOO_INPUT_EXCLUSIVE one (MQRC_OBJECT_IN_USE), queue
  depth limits (MAXDEPTH, MAXMSGL), expiry.

- **IBM (document).** IBM MQ Application Programming Reference, MQOPEN and the MQOD structure (an unknown ObjectName
  returns MQRC_UNKNOWN_OBJECT_NAME, 2085), and the IBM MQ local-queue attributes in the DEFINE QLOCAL reference
  (MSGDLVSQ, default FIFO or PRIORITY by queue; DEFPRTY, default 0; DEFPSIST, default NO)
  (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-mqopen-open-object). The wording is paraphrased, not
  verbatim.
- **Declared difference.** A queue's MSGDLVSQ is modelled as PRIORITY for every queue. IBM's default for a queue is
  FIFO, so a case that relies on arrival order across priorities states it and is judged against the model, not z/OS.

### W4. Identifiers the queue manager makes — MsgId and object handles, deterministic on both sides
- **IBM.** A put with MsgId MQMI_NONE gets a unique MsgId from the queue manager, returned in the MQMD; its form is
  the queue manager's own. An object handle is an opaque value.
- **Assumed.** Both models make the MsgId `GGMQ` followed by a 20-digit counter (and a stated message with no MsgId
  `GGMQSTATED` and its number), and the handles 1, 2, 3 ... in the order opened; MQCLOSE sets the handle to
  MQHO_UNUSABLE_HOBJ (-1), as IBM documents. A program that depends on the form of either (rather than its identity)
  would differ from z/OS; no modelled program does.
- **Not modelled.** MQPMO_NEW_MSG_ID / NEW_CORREL_ID (refused by name), MsgId / CorrelId matching on MQGET (a get
  whose MQMD carries an id other than MQMI_NONE / MQCI_NONE is refused), message groups and segments.

- **IBM (document).** IBM MQ Application Programming Reference, the MQMD structure (MsgId: the queue manager
  generates a unique id when MQMI_NONE is given) and MQCLOSE (the handle is set to MQHO_UNUSABLE_HOBJ)
  (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-mqmd-message-descriptor). The wording is paraphrased, not
  verbatim.
- **Declared difference.** The `GGMQ` + 20-digit MsgId form and the handle numbers 1, 2, 3 are the models', not
  z/OS's. IBM does not define the form, so the comparator expects the two models to agree with each other only.

### W5. The unit of work — MQ's is the CICS task's: SYNCPOINT commits, ROLLBACK and an abend back out, the task's end commits
- **IBM.** Under CICS the MQ unit of work is the task's: EXEC CICS SYNCPOINT commits it, SYNCPOINT ROLLBACK and an
  abend that ends the task back it out, and the task's normal end commits it. On z/OS a get or put with neither
  SYNCPOINT option is within the unit of work. A message put in a unit of work is not available until it commits; one
  got in it is restored by a backout with its MQMD BackoutCount raised by one.
- **Modelled.** ggcics.c's `uow_end` (SYNCPOINT, ROLLBACK, abend backout) tells ggmq.c (`ggmq_uow_end`, a weak hook as
  ggsql's); CicsTask tells its joined resource managers at the same three points (`withResource`, #4892); both
  models commit at the task's normal end before the queues it leaves are compared (the `MQ-QUEUES` event).
- **Assumed.** That the task's normal end is a commit for every program, as CICS documents for a task ending with
  RETURN; a SYNCPOINT ROLLBACK after a SYNCPOINT stays refused by CicsTask as before.
- **Not modelled (refused).** MQCMIT, MQBACK, MQBEGIN (an MQ unit of work of its own), MQGMO_SYNCPOINT_IF_PERSISTENT,
  MQGMO_MARK_SKIP_BACKOUT, backout thresholds and requeueing.

- **IBM (document).** IBM MQ Application Programming Guide, using MQ in a CICS program (the MQ unit of work is the
  CICS task's; SYNCPOINT commits, SYNCPOINT ROLLBACK backs out), and the IBM MQ Application Programming Reference,
  MQGMO (MQGMO_SYNCPOINT, MQGMO_NO_SYNCPOINT) and the MQMD BackoutCount field
  (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-mqgmo-get-message-options). The wording is paraphrased, not
  verbatim.
- **Declared difference.** None for the modelled points. The one assumption (the task's normal end commits for every
  program) is stated above; the refused calls are not a difference, they are not run.

### W6. MQI outside the modelled calls — batch MQ, the other verbs, a connection handle
- **Modelled.** MQOPEN, MQGET (destructive), MQPUT, MQPUT1 and MQCLOSE from a CICS program, every parameter BY
  REFERENCE, each MQLONG a fullword BINARY item (`gitgalaxy/standards/mq.py`, `det/mq.py`). Under CICS no MQCONN is
  needed and Hconn is MQHC_DEF_HCONN (0); any other Hconn is refused (it would come from MQCONN).
- **Refused by name.** A CALL of MQCONN, MQCONNX, MQDISC (batch MQ: a connection of its own), MQBEGIN / MQCMIT /
  MQBACK, MQINQ / MQSET, MQSUB / MQSUBRQ, MQCB / MQCTL, MQSTAT and the message-handle calls is a translation hole
  naming why; an MQI call from a batch program is a hole; a COMP-5 or halfword MQLONG is a hole (a native binary item
  is little-endian on the oracle). Every option bit outside the modelled set, Report options, and MQCLOSE options other
  than MQCO_NONE stop the run by name on both sides.
- **Burned estates (#5278).** The MQI calls the burned programs make are MQOPEN, MQGET, MQPUT1 and MQCLOSE (CardDemo
  CODATE01, COACCT01, COPAUA0C), all modelled; none calls MQINQ or MQSET (`test_det_mq.py`). COPAUA0C is not held
  by MQ.
- **COPAUA0C translates with no MQ hole (#5278).** Under CICS its MQOPEN / MQGET / MQPUT1 / MQCLOSE and the CMQ* layouts
  translate; the options it builds (MQGMO NO-SYNCPOINT + WAIT + CONVERT + FAIL-IF-QUIESCING, MQPMO NO-SYNCPOINT +
  DEFAULT-CONTEXT, MQOO INPUT-SHARED, MQCO NONE) are inside the modelled sets. Measured (#5278, det_survey on the
  generated CardDemo estate, with C17's run-time guard): 344 of 344 statements translate, no hole, and the port
  compiles. Its three READ KEYLENGTH(LENGTH OF ...) forms are the file's full key on mapped files, so they are no
  hole; they were one only when the file was unmapped (the stub-only translation in `test_det_mq.py`). EXEC DLI (I5)
  and the INITIALIZE REPLACING of a table (C17) no longer hold it. The `missing copybook CMQGMOV` rows in
  `blockers_history.jsonl` are from before #5236 and do not reproduce.

### W7. MQGMO_CONVERT — a no-op where the message is already as asked, refused otherwise
- **IBM.** MQGMO_CONVERT converts the application data to the CodedCharSetId and Encoding the MQMD asks for, by the
  message's Format; MQCCSI_Q_MGR is the queue manager's CCSID.
- **Modelled.** When the message is already in the CCSID and encoding asked for there is nothing to convert. The queue
  manager's CCSID is a case fact (default 37, the region's page, X-family default); a put with MQCCSI_Q_MGR stores the
  message with it, as IBM does.
- **Refused.** Any real conversion (another CCSID or encoding): data conversion exits and the built-in MQFMT_STRING
  conversion are not modelled. Note the oracle's message bytes are in the case's data page (Latin-1), the CCSID is a
  label both sides carry alike.

### W8. Put context — PutDate / PutTime from the pinned clock, the identity fields placeholders
- **IBM.** With MQPMO_DEFAULT_CONTEXT (also when no context option is given) the queue manager sets the message's
  identity context (UserIdentifier, AccountingToken, ApplIdentityData) and origin context (PutApplType, PutApplName,
  PutDate and PutTime in GMT, ApplOriginData) and returns them in the MQMD; with MQPMO_NO_CONTEXT both are blank.
- **Modelled / assumed.** PutApplType is MQAT_CICS (1); PutDate / PutTime (YYYYMMDD, HHMMSSTH) are the case's pinned
  clock, taken as GMT; ApplIdentityData and ApplOriginData blank. UserIdentifier (blanks), AccountingToken (nulls) and
  PutApplName (blanks) are placeholders: on z/OS they are the task's user id, an accounting token and the CICS
  application name, which the case does not state. A program that reads them after a put is judged against the
  placeholders; no modelled program does. MQPMO Known/Unknown/InvalidDestCount are not written (IBM sets them for
  distribution lists); ResolvedQName / ResolvedQMgrName are.
- **Not modelled (refused).** MQPMO_PASS_*_CONTEXT and SET_*_CONTEXT on a put.
- **The trigger message.** A triggered transaction's MQTM (RETRIEVE INTO the CMQTML layout) is a case fact
  (`start_data`, #4892), given to both sides as the task's START data.

- **IBM (document).** IBM MQ Application Programming Reference, MQPMO (MQPMO_DEFAULT_CONTEXT, MQPMO_NO_CONTEXT) and
  the MQMD identity and origin context fields (UserIdentifier, AccountingToken, PutApplType, PutApplName, PutDate,
  PutTime) (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-mqpmo-put-message-options). The wording is
  paraphrased, not verbatim.
- **Declared difference.** UserIdentifier, AccountingToken and PutApplName are placeholders, and PutDate / PutTime
  are the pinned case clock: z/OS fills them from the running task and the real clock.

## The Java side

### J1. Files on H2 — ASSUMED
- **What.** The proofs run the generated project's `h2` target: VSAM files become H2 tables read through the entities'
  record codecs, and Db2 repositories run on the real Db2.
- **Not proven.** Another target database (Postgres, Oracle) brings its own collation and type behaviour.

- **IBM (document).** The IBM side of a VSAM file is DFSMS Using Data Sets (VSAM KSDS, ESDS and RRDS organizations,
  key order and record access), with the CICS file-control behaviour in the CICS TS Application Programming Reference.
  The wording is paraphrased, not verbatim.
- **Declared difference.** H2 tables are not VSAM data sets. Key order, duplicate-key and not-found conditions are
  carried by the record codecs and compared with the oracle's files; they are not measured on z/OS. Another target
  database's collation and type behaviour is outside the proofs (above).

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
- **Assumed.** The SQLCA a derived fault leaves is reset's: SQLCODE and SQLSTATE set, SQLERRMC empty (SQLERRML 0),
  SQLERRD zero, no warnings. A declared `sql_faults` entry may also carry `sqlerrmc` (one token of 1 to 70 non-space
  characters, with SQLERRML) and `sqlerrd3`, set to the same bytes on both sides (#5794); the token is not judged
  against z/OS (-913's first token is the reason code; other tokens and X'FF' separators are not modelled). SQLERRP,
  the other SQLERRD and SQLWARN stay unmodelled. A derived fault on a program that does `SQLERRMC(1:SQLERRML)` (CBSA
  BANKDATA) is refused by name (X8: a length-0 reference modification), so its reason arms run as declared faults.
  -913 rolls back the statement only; -911's unit-of-work rollback is not used. Nothing else changes: no row, no host
  variable, a cursor where it was.
- **Not judged.** A fault task that LINKs to a program the case does not run is judged up to that LINK (X6). One whose
  path reaches a det port's named hole (formerly COTRTLIC's CALL DSNTIAC, now modelled, Q5) is recorded "not judged" and left out of the proof
  and of the coverage figure. A port without DetSql (a model port) cannot take a planned SQL fault: such a task is
  recorded "not judged" (no SQL fault hook), never run unfaulted.
- **Effect.** Coverage of the 17 Db2 cases before and after is in the #4173 PR, e.g. GenApp LGACDB01 6/14 → 8/14
  branches, LGUPDB01 17/38 → 26/38, CBSA DELACC 10/14 → 13/14.

- **IBM (document).** Db2 13 for z/OS SQL Reference, SQL communication area (SQLCA): SQLCODE, SQLSTATE, SQLERRMC with
  SQLERRML, SQLERRD and SQLWARN; and Db2 13 for z/OS codes for -803 (duplicate key on a unique index), +100 (no row
  found) and -913 (unsuccessful execution caused by deadlock or timeout, reason code in the first SQLERRMC token),
  https://www.ibm.com/docs/en/db2-for-zos/13?topic=reference-sql-communication-area-sqlca. The wording is
  paraphrased, not verbatim.
- **Declared difference.** A fault is injected, not raised by Db2, so the SQLCA is the stub's: SQLERRMC empty unless
  declared, SQLERRD zero, SQLERRP and SQLWARN unmodelled, where Db2 fills them per code. -913 rolls back the
  statement only, as the Db2 code documents; -911 (unit-of-work rollback) is not used.

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
- **An entry that claims a match** (ASSUMED, MATCHED, or no status) names an IBM document number (`SC27-8713-03`) or an
  `ibm.com/docs` link, declares the difference, or states that IBM is silent (#4702). `python tests/tools/register.py
  audit --ci` fails on one that does not; `STRICT_BASELINE` lists those that still name a document only by name, and
  only shrinks.
- **How.** This page is generated; do not edit it. Each entry is one file, `docs/language_status/register/<ID>.md`
  (front matter: id, family, status, title, area, summary, reached; then the entry text). Take a new ID with
  `python tests/tools/register.py next <family>` when the issue is filed, so parallel PRs never pick the same number
  (`new <ID>` writes a skeleton). Prose sections live in `register/_parts/`, the page order in `register/_layout.json`.
  Commit the entry file only: this page is not committed (#5057). A PR's CI renders it (it must render, the same way
  twice) and shows the diff; after merge it is published to the `generated` branch. `python tests/tools/register.py
  render` writes a local copy to read.

### z/OS calibration
0 of 140 entries have a measured z/OS result (none: the IBM side stays as the entry states it; no z/OS run is recorded).
