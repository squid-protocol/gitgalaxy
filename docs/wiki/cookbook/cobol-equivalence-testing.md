---
description: "Three recipes for the equivalence harness: prove a port equivalent on generated inputs, test an estate that ships no data, and (planned) guard a COBOL change against drift."
---
# Cookbook: COBOL Equivalence Testing

A migrated program is only done when it behaves like the original. The equivalence harness runs the original COBOL, records its outputs, runs the replacement on the same inputs and compares them field by field. Nobody writes expected values: the original's outputs are the answer key. The [explainer](../05-20-equivalence-harness.md) covers the pipeline and its limits. These recipes show how to run it.

Every output below was produced by running the command, trimmed where noted. Recipe 3 is planned and has no commands.

## Setup

You need Docker (the GnuCOBOL image is built from `tests/equivalence/gnucobol.Dockerfile`), JDK 17, Maven, and a checkout of the CardDemo corpus. Run from the GitGalaxy repo root.

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 PATH=$JAVA_HOME/bin:$PATH
export GITGALAXY_MAINFRAME_CORPORA=/path/to/.mainframe_corpora   # holds aws-mainframe-modernization-carddemo/ ...
python tests/tools/equivalence.py list                           # every case
```

## Recipe 1: Prove a port is equivalent, on generated inputs

**The case.** A case is `tests/equivalence/<name>/case.json`. Setting a dataset's `"input"` to `"@generate"` builds its records from the copybook layout instead of reading a shipped file. This is [`carddemo-intcalc-generated`](https://github.com/squid-protocol/gitgalaxy/blob/main/tests/equivalence/carddemo-intcalc-generated/case.json) (CardDemo's interest calculation, CBACT04C), shortened:

```json
{
  "corpus": "aws-mainframe-modernization-carddemo",
  "program": "CBACT04C",
  "program_source": "app/cbl/CBACT04C.cbl",
  "copy_dirs": ["app/cpy"],
  "port_from": "carddemo-intcalc",
  "job": "INTCALC", "step": "STEP15", "parm": "2022071800",
  "clock": "2022/07/18 10:30:15.00",
  "datasets": {
    "ACCTFILE": {
      "input": "@generate", "organization": "indexed", "reclen": 300,
      "keys": [{"offset": 0, "length": 11}], "entity": "AccountRecord", "compare": true,
      "copybook": "app/cpy/CVACT01Y.cpy",
      "generate": {"copybook": "app/cpy/CVACT01Y.cpy", "record": "ACCOUNT-RECORD",
                   "records": 30, "seed": 3804,
                   "fields": {"ACCT-GROUP-ID": {"values": ["DEFAULT", "GRPA", "GRPB", "GRPZ"]}}}
    },
    "XREFFILE": {
      "input": "@generate", "organization": "indexed", "reclen": 50,
      "keys": [{"offset": 0, "length": 16}, {"offset": 25, "length": 11, "duplicates": true}],
      "entity": "CardXrefRecord",
      "generate": {"copybook": "app/cpy/CVACT03Y.cpy", "record": "CARD-XREF-RECORD",
                   "records": 30, "seed": 3804,
                   "fields": {"XREF-ACCT-ID": {"from": "ACCTFILE.ACCT-ID"}}}
    },
    "TRANSACT": {"organization": "sequential", "reclen": 350, "compare": true,
                 "copybook": "app/cpy/CVTRA05Y.cpy"}
  }
}
```

Reading it:

- `records` and `seed` fix how many records and which ones: the same case gives the same inputs on every run.
- `keys` tell the loader how the VSAM file is keyed. The first key is made unique, and the file is loaded in key order.
- `fields` steers the generator. `values` picks from a list. `from` draws a field from another dataset's values, so every cross-reference points at a generated account. A `miss` rate (not used here) makes some joins miss on purpose. Fields you do not steer get edge values for their PICTURE.
- `compare: true` marks the outputs to compare. `TRANSACT` is written by the program, so it has no input.
- `port_from` says which committed port to prove (here the hand-written `carddemo-intcalc` port).

**Look at the COBOL side first.** `--cobol-only` runs only the original and prints what it produced:

```bash
python tests/tools/equivalence.py run carddemo-intcalc-generated --cobol-only --keep /tmp/intcalc-cobol
```
```text
ACCTFILE: 9000 bytes, 30 records
TRANSACT: 12950 bytes, 37 records
SYSOUT: 2596 bytes, 58 lines
RETURN-CODE: 0
```

**Prove the port.**

```bash
python tests/tools/equivalence.py run carddemo-intcalc-generated --keep /tmp/intcalc
```
```text
 ... (the project scaffold's progress lines are omitted) ...
CBACT04C RETURN-CODE: COBOL 0, Java 0
CBACT04C ACCTFILE: 30/30 records equal
CBACT04C TRANSACT: 37/37 records equal
CBACT04C SYSOUT: 58/58 lines equal
CBACT04C COBOL coverage: proven on 1 run, covering 20/22 paragraphs and 49/86 branches
report: /tmp/intcalc/report.json
```

The command exited 0 here. `--keep DIR` keeps the work directory, with the COBOL and Java projects, `report.md`, `report.json` and `coverage.json`.

**Reading the result.**

- **Records equal.** `30/30` means all 30 account records, after the run, match field by field. `TRANSACT` is the transactions the program wrote: 37 on both sides. `SYSOUT` is every DISPLAY line.
- **Coverage.** `20/22 paragraphs and 49/86 branches` is what the one run exercised in the COBOL. It is not a score of the port. `report.md` lists what was not reached:

  ```text
  Live code no run reached:
  - paragraph `9999-ABEND-PROGRAM` (line 628)
  - paragraph `9910-DISPLAY-IO-STATUS` (line 635)
  - IF at line 189: never false
  - IF at line 237 in `0000-TCATBALF-OPEN`: never false
  ```

  The unreached paragraphs are the abend and I/O-status handlers: this case never makes a file fail. A fault case (`"faults"` in `case.json`) injects a file status at a statement on both sides and covers them. Proven here means proven on this run, and these branches are unchecked.
- **Key order.** `report.md` states `ASCII / ISO-8859-1 byte order on both sides, not the mainframe's EBCDIC order`. Both sides sort the same way, so this run agrees, but on a mainframe records whose keys mix letters and digits would be read in another order.
- **The oracle.** `report.json` records `cobc (GnuCOBOL) 3.1.2.0`, the image id, and whether it matches the pin.

The hashed evidence record for a committed case, and mutation testing (how many deliberately broken ports the proof still catches), are separate steps. See [evidence records](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/evidence_records.md) and [mutation testing](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/mutation_testing.md). This recipe did not run them.

## Recipe 2: Test an estate that ships no data

> This recipe depends on [PR #4492](https://github.com/squid-protocol/gitgalaxy/pull/4492) (draft, issue #3804). `mortgage-mlist-generated` is not on `main` yet. The output below was produced from that PR's branch.

IBM's DBB mortgage application ships COBOL, copybooks and no data files. The case `mortgage-mlist-generated` (CICS program EPSMLIST, transaction EPSP) builds everything it needs. A shortened view:

```json
{
  "kind": "cics", "corpus": "dbb-mortgage-application", "program": "EPSMLIST",
  "transid": "EPSP", "linked": true,
  "datasets": {
    "EPSMORTF": {
      "input": "@generate",
      "copybook": "zBuilder/MortgageApplication/copybook/epsmortf.cpy",
      "record": "MORTGAGE-COMPANY-INFO",
      "csd": {"organization": "ESDS", "reclen": 56, "why": "the repository ships no CSD or IDCAMS DEFINE for EPSMORTF ..."},
      "generate": {"records": 12, "seed": 3804, "fields": {"MORT-FILE-RATE": {"values": [20, 25.5, 99.99, 20.01]}}}
    }
  },
  "scenario_generate": {
    "seed": 3804, "count": 12, "prefix": "generated", "aid": "DFHENTER",
    "commarea": {"PROCESS-INDICATOR": "9",
                 "EPSPCOM-PRINCIPLE-DATA": {"edge": true},
                 "EPSPCOM-NUMBER-OF-YEARS": {"edge": true},
                 "EPSPCOM-YEAR-MONTH-IND": {"values": ["Y", "M"]}}
  }
}
```

Two things differ from recipe 1. The estate ships no CSD, so the case states the file's shape (an ESDS of 56-byte records) and why. And the scenarios are generated too: `scenario_generate` builds 12 COMMAREAs, with `edge` using each field's PICTURE edge values.

EPSMLIST has no hand-written port, so the proof goes through the deterministic translator (`det_port.py`), from a checkout of the #4492 branch:

```bash
python tests/tools/det_port.py run mortgage-mlist-generated --work /tmp/mlist
```
```text
 ... (refraction and scaffold progress lines omitted) ...
mortgage-mlist-generated     51/51 translated  DIFFERS
```

The line says 51 of 51 statements translated (no holes), and the verdict is **DIFFERS**. That verdict is expected on that branch, and it is worth reading closely. `/tmp/mlist/mortgage-mlist-generated/proof/report.md` shows:

```text
| scenario | events equal | total |
| generated-01 | 4 | 4 |
 ...
| generated-12 | 4 | 4 |

## Through the deployed entry points (java-facade, #4449)
| generated-01 | 0 | 4 | EPSMLIST.handleLink | refused: handleLink of EPSMLIST threw before it ran
  the scenario's task: java.lang.UnsupportedOperationException: handleLink: this port runs as runTask |
```

- The `runTask` side is equal on all 12 generated scenarios (4 events each).
- The java-facade side is refused for all 12: the det translator's facade is a stub that throws. This is tracked in [#4465](https://github.com/squid-protocol/gitgalaxy/issues/4465), and the case is listed in `det_sweep_baseline.json` for it. A CICS case is proven only when both sides pass, so the overall verdict is DIFFERS.
- COBOL coverage in `report.json`: 5 of 6 live paragraphs and 7 of 15 branches. Twelve generated scenarios reach less than half of the branches.

## Recipe 3: Guard a COBOL change against drift (PLANNED, [#4513](https://github.com/squid-protocol/gitgalaxy/issues/4513))

**Not built. There are no commands to run yet.** This describes the intended flow.

A CICS developer changes a COBOL program that stays on the mainframe and wants proof that only the intended outputs changed. The same generated scenarios would serve:

1. Generate scenarios for the program and commit the original's outputs as an approved baseline.
2. On every change, re-run them. Any changed output is flagged with its scenario and field.
3. A person approves intended differences, scoped, for example "only LATE-FEE, only for overdue accounts". This builds on declared differences ([#4051](https://github.com/squid-protocol/gitgalaxy/issues/4051)), not a second mechanism.
4. Anything not approved fails the check.

This would show that behaviour is **unchanged**, not that it is correct: existing bugs are part of the baseline. Running the original on z/OS needs [#4050](https://github.com/squid-protocol/gitgalaxy/issues/4050). The done condition is a demo PR that changes one program, and shows the approved difference passing and an unintended side effect caught.

## Related
- [The Equivalence Harness](../05-20-equivalence-harness.md)
- [Proven COBOL-to-Java Ports](../05-19-proven-cobol-to-java-ports.md)
- [Batch Test Harness](../05-06-batch-test-harness.md)
