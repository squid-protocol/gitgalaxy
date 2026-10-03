# Third-party CardDemo ports through the equivalence harness: Lightyear and SENTINEL IDE

Run 2026-10-03 with `tests/tools/thirdparty_port.py`. The pattern is that of the IBM WCA4Z experiment
(`ibm_wca4z_lgacdb01.md`, #4177) and Devin's eval arms (`devin-carddemo-harness.md`, #4190): a port is fetched at a
pinned commit, built as it ships, run on the inputs one of our proven cases gives GnuCOBOL, and judged by the
harness's own comparison. This is an observation, not a ranking. Both projects describe their work honestly in their
own terms (quoted below), and each is judged against what it attempted.

Neither repository carries a licence. Nothing of theirs is committed here; this document quotes a few lines only.

| Port | Repository @ commit | What it is |
|---|---|---|
| Lightyear | `howardweale/lightyear-carddemo-modernization` @ `e24d77822f70` | A Spring Batch candidate for CBACT04C in `candidate-java/`. Its README: "It deliberately remains behind the repository's Python oracle and comparator", and elsewhere: "Native coverage and equivalence remain unobserved." |
| SENTINEL IDE | `noahlabsai/aws-mainframe-modernization-carddemo-JAVA` @ `47af18641ee6` | A full CardDemo translation, "1:1 mapping of COBOL programs to Java classes", by SENTINEL IDE (NOAH Labs). |

## Summary

| Port | Program (our case) | Base runs, 6 JVM environments | Missing-input runs (status 35 at OPEN) |
|---|---|---|---|
| Lightyear | CBACT04C (`carddemo-intcalc`) | **Data equal** in 4 of 6 environments (ACCTFILE 52/52, TRANSACT 53/53, RC 0). Arabic and Thai differ (locale). No SYSOUT DISPLAYs, by design. | 0 of 4 match: the job ends FAILED, publishes nothing, **exits 0** (COBOL: message, status 35, ABEND U0999) |
| SENTINEL | CBACT02C (`carddemo-readcard`) | Job log differs: 2/52 lines (records logged as Java `toString()`) | 1 of 1 match (ABEND U0999, same messages) |
| SENTINEL | CBACT03C (`carddemo-readxref`) | Job log differs: 2/102 lines (the same) | 1 of 1 match |
| SENTINEL | CBCUS01C (`carddemo-readcust`) | Job log differs: 1/102 lines (the same) | ABEND matches; 1 message worded differently |
| SENTINEL | CBACT04C (`carddemo-intcalc`) | Differs: **abends U0999** on the first account (COBOL ends RC 0) | 4 of 4 ABEND U0999; 1 message spaced differently |
| SENTINEL | CBTRN02C (`carddemo-posttran`) | Differs in every output: all 305 daily transactions rejected (COBOL: 264 posted, 41 rejected, RC 4) | 3 of 4 ABEND U0999 (1 message worded differently each); TCATBALF absent: no abend |
| Devin eval arm A | CBACT04C, CBTRN02C | (#4190: data equal in 4–6 environments) | 0 of 8 match: exit status 12, file path on stderr, no "ERROR OPENING" message, no status |
| Devin eval arm B | CBACT04C, CBTRN02C | (#4190: data equal) | 0 of 8 match: exit status 1, a Java stack trace |

"Match" is the harness's own verdict: same ABEND code (or RETURN-CODE) and, after an abend, the job log line by line.

## Comparison tiers

- **full:** `compare_run` as for our own ports: RETURN-CODE or ABEND, every compared data set field by field per its
  copybook, and SYSOUT line by line.
- **data:** the same without SYSOUT. This is the fair tier for Lightyear, which writes Spring's log and a JSON
  receipt, not the COBOL's DISPLAY lines. For CBACT02C, CBACT03C and CBCUS01C the case compares *only* SYSOUT (the
  programs DISPLAY each record), so their data tier checks nothing but the return code and is not reported as a
  result.
- **clock-masked:** the data tier, after a port that reads the wall clock (SENTINEL: `LocalDateTime.now()`, no clock
  seam) has its run-time timestamp fields set to the COBOL side's. Only a DB2-format timestamp within a day of the run
  is masked (register M4's rule). Fields: CBACT04C TRANSACT `TRAN-ORIG-TS`, `TRAN-PROC-TS`; CBTRN02C TRANFILE
  `TRAN-PROC-TS`. For both SENTINEL programs the masked tier still differs, for the reasons below.

## Root causes

### Lightyear, CBACT04C
- **Default, Turkish, German, Hindi: data equal.** Every account and generated transaction matches byte for byte,
  and the return code matches. This is the "unobserved" equivalence its README names, now observed for these base
  runs on our case's 52 accounts and 50 balances.
- **Arabic and Thai: a locale defect.** `String.format("%0" + width + "d", scaled)` (`codec/ZonedDecimal.java:47`)
  and `"%06d".formatted(suffix)` (`service/InterestCalculationService.java:94`) format digits with the JVM default
  locale. Under ar-EG and th-TH that gives non-ASCII digits, which the ASCII record writer cannot carry. It's the same
  class of defect as Devin's (#4190).
- **Missing input: a failure the exit status does not show.** `DatasetIo.read` throws "Required dataset does not
  exist", and Spring Batch records the job as FAILED and publishes no output (its documented all-or-nothing
  publication holds). But the process exits **0**: Spring Boot's default exit code for a failed batch job. A scheduler
  reading the return code would see success. The COBOL displays the error and file status and ABENDs U0999.

### SENTINEL IDE
- **CBACT02C, CBACT03C, CBCUS01C: data correct, job log not.** The COBOL `DISPLAY CARD-RECORD` writes the record's
  bytes. The port logs a Java object (`CVACT02Y{cardNum='0500024453765740', acctId=50}`), so the job log differs on
  every record line. On a missing file both sides display the same error and status and ABEND U0999.
- **CBACT04C: `XREF-ACCT-ID` read at the wrong offset.** CVACT03Y is `XREF-CARD-NUM X(16)`, `XREF-CUST-ID 9(09)`,
  `XREF-ACCT-ID 9(11)`: the account is at offset 25. The port reads `s.substring(16, 27)` (the customer ID and two
  account digits) when loading its cross-reference map. No account then has a cross-reference, the first lookup fails
  with status 23, and the program ABENDs U0999 where the COBOL ends RC 0.
- **CBTRN02C: a one-byte shift in the daily transaction record.** CVTRA06Y's `DALYTRAN-AMT` is `S9(09)V99`, 11 bytes
  of zoned decimal. The port reads 12 (`s.substring(132, 144)`) and parses it as a plain decimal, so every later field
  is one byte off, including the card number (`substring(263, 279)`, where the copybook puts it at 262). Every card
  lookup fails, and all 305 transactions are rejected with reason 100 "INVALID CARD NUMBER FOUND". The COBOL posts
  264 and rejects 41 (38 with reason 102, 3 with 103). The same program also:
  - reads `XREF-ACCT-ID` at offset 16, as CBACT04C does (`xs.substring(16, 27)`);
  - writes reject records as a formatted line (the amount as `%012.2f`, then `" " + code + " " + description`), 361
    bytes against the copybook's 430 (the 350-byte transaction, a 4-digit code, a 76-byte description);
  - keys TCATBALF on `line.substring(0, 26)` where the record's key is 17 bytes. Seen in the code; its effect is not
    isolated here, because the rejections above come first.
- **Missing TCATBALF (CBTRN02C): treated as empty.** The port opens it only `if (f.exists())`, so the run continues.
  The COBOL's OPEN I-O fails with status 35 and ABENDs U0999.

### Devin's eval arms: the external-fault experiment
Both arms match the COBOL on base runs (#4190). With an input file absent:
- **Arm A** exits with status 12 and prints the missing path on stderr. Its SYSOUT has only "START OF EXECUTION…":
  no "ERROR OPENING …" message and no file status.
- **Arm B** exits with status 1 and a Java stack trace.
- **The COBOL**, in all 8 runs, displays the specific open error and `FILE STATUS IS: NNNN0035`, then ABENDs U0999.

This turns the structural observation in the survey ("error paths collapsed and unexercised") into measured
behaviour: the failure is still detected, but reported differently from the COBOL, in code, message and status.

## The adapter, exactly

`tests/tools/thirdparty_port.py` and `tests/tools/thirdparty/adapter`; nothing else:
- **Inputs:** the case's input data sets as text, one record per line. Both ports read lines: Lightyear with
  `Files.readAllLines`, SENTINEL with `BufferedReader.readLine`. These are the bytes GnuCOBOL is given, an indexed
  set in primary-key order (as a KSDS unloads), each record followed by a newline. Both ports' shipped sample data
  uses the same layouts.
- **Outputs:** the lines a port wrote, each the record's length, joined back into fixed records; an indexed output in
  key order. A line of another length is not padded or cut. It is compared as written, and the framing difference is
  recorded (SENTINEL's 361-byte reject records).
- **Lightyear:** its Spring Boot jar run with its documented properties (`--carddemo.input-dir`, `output-dir`,
  `processing-date` from the case's PARM, `timestamp` from the case's frozen clock in DB2 format). When it publishes
  nothing, the account master is the one it was given (its in-place file is unchanged).
- **SENTINEL:**
  - Its program classes have no `main`. `ProgramLauncher` constructs one with its String file paths (and PARM) and
    calls `execute()`, as the port's own unit tests do.
  - An exception carrying "ABCODE n" (its `9999-ABEND-PROGRAM`) is reported as ABEND Unnnn.
  - logback is pointed at a message-only layout on stdout, so its log lines read as the job log.
  - The project as shipped does not compile: 18 errors, all in `screen/MainMenuScreenController`,
    `config/BatchConfig` and `screen/SessionCommArea`, which no batch program uses. The five program classes are
    compiled as they are, with `javac -sourcepath`, against the project's declared dependencies.
- **Environments:** the JVM default locale and time zone of each harness environment (#3821), set before the port's
  code runs.
- **Not applied:** the cases' injected fault runs. Neither port has an I/O seam, and adding one would change their
  code. Instead, each case fault that is an input OPEN failing with status 35 is reproduced from outside (the file
  is absent) and compared with that COBOL fault run.

## Not run, and why

| Port | Program | Why |
|---|---|---|
| SENTINEL | CBTRN01C, CBTRN03C | The constructors take `SeqFileReader` / `IndexedFileReader` / `ReportWriter` interfaces, with records as `Map<String,Object>`, and the port ships no implementation. Supplying one would mean writing its file I/O and record decoding: translation work, not an adapter. |
| SENTINEL | COBTUPDT (Db2) | Its port uses Spring Data JPA against the app's own schema; not attempted in this pass. |
| Lightyear | COACTVWC | `CicsVsamAccountViewService` is a read-only lookup with no CICS task, COMMAREA or BMS map. Our case compares the screen and COMMAREA a CICS task produces, so an adapter would have to write the screen logic. Its README says as much: it "does not claim to emulate CICS task semantics". |

## Caveats

- **Base runs only.** The base runs cover 49/86 branches (CBACT04C), 55/96 (CBTRN02C) and 13/22 (each of the
  three read programs). Our own ports are proven on these plus every injected fault run.
- **Missing-file faults stand in for status 35.** A missing file is how an OPEN fails with status 35 outside a
  mainframe. On z/OS a missing DD usually fails at allocation instead. The comparison is with the case's declared
  status-35 fault run.
- **Our oracle is GnuCOBOL, not z/OS.** See `oracle_assumptions.md`.
- **Lightyear's comparator was not used.** Its own oracle and comparator (Python, in the same repository) may define
  equivalence differently; our verdict is the harness's.

## Reproducing

```sh
# environment: .claude/skills/det-port/SKILL.md (JAVA_HOME 17, corpora, licence key, Docker)
python tests/tools/thirdparty_port.py --work <scratch> --port lightyear,sentinel --external-faults
python tests/tools/thirdparty_port.py --work <scratch> --port devin --jdk21 <a JDK 21>   # eval arms, external faults
```
