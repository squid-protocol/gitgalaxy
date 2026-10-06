#!/usr/bin/env python3
"""
Behavioural equivalence harness (#3624): the original COBOL and the generated Java
run on the same recorded inputs, and their outputs are diffed record by record,
field by field, decimals exact.

    python tests/tools/equivalence.py run <case> [--keep DIR]
    python tests/tools/equivalence.py list

A CASE (tests/equivalence/<case>/case.json) names a corpus program, the datasets it
reads and writes (per DD: the corpus data file, record length, VSAM keys, the
copybook that lays the record out), the step's PARM, and the pinned clock.
A dataset's input may be `@generate` (#3804, equivalence_inputs.py): records built from
its copybook layout -- edge values per PICTURE, unique sorted keys, joins drawn from the
files they must meet -- so an estate that ships no data can be proven too.

COBOL side -- GnuCOBOL 3.x (BDB indexed files) in a container built from
tests/equivalence/gnucobol.Dockerfile. Each KSDS input is loaded by a generated
loader keyed like the program's SELECT (alternate keys included); the program runs
under a generated driver that passes the JCL PARM through LINKAGE, with
COB_CURRENT_DATE pinning FUNCTION CURRENT-DATE; each output (and each KSDS the
program opens I-O) is unloaded to fixed-length records. Compiled `-std=ibm
-fsign=EBCDIC`: the corpus data is EBCDIC-style zoned (`{` = +0) in ASCII text.
#3828: the program's CBL / PROCESS cards, and a case's `"compiler_options": ["TRUNC(BIN)"]`
(the compile step's PARM; the cards override it), become cobc flags where GnuCOBOL has one
(TRUNC(BIN) -> -fnotrunc); one it cannot honour -- INTDATE(LILIAN), ARITH(EXTEND),
TRUNC(OPT), NUMPROC(MIG) under a compiler before Enterprise COBOL 5 -- stops the run
(equivalence_common.compile_options); NUMPROC(PFD) runs only with a det port (#4271). A case's
`"culture"` (e.g. {"db2_date_format": "eur"}) is the Java side's target config.

Java side -- the generated project (the refractor + cobol-to-java pipeline, target
config `h2`) with the case's hand-ported sources overlaid (the vertical slice), run
by a generated JUnit test: inputs are loaded through the entities' record codecs
into H2, the step's `runBatch(dds)` runs, outputs are dumped through the same
codecs and the DatasetResolver's files.

Diff -- per output: records paired in order (a KSDS in key order), every field of the
copybook layout compared -- numeric DISPLAY / COMP-3 / COMP as exact decimals,
everything else byte for byte. The report gives, per program, records equal /
total and every differing field.

#3821 -- one claim, many environments: `--environments turkish,thai` (or `all`, or a case's
`"environments"`) runs the Java side under each JVM default locale / time zone
(equivalence_java.ENVIRONMENTS, or `LOCALE/TZ` as written) and diffs every run against the one
COBOL run. The report says which environments and which key order the claim covers.

#3815 -- declared encodings: `--source-encoding` / a case's `"source_encoding"` (how the COBOL
sources are read; default the engine's read_source ladder) and `--data-encoding` / `"data_encoding"`
(the record bytes' code page -- inputs, generated records, outputs, the diff and the Java side's
record Charset; default Latin-1, as before). See equivalence_common.

#4023 follow-up -- fault runs: a case's `"faults"` ([{name, plan: [{dd, op, nth, status}], why}]) each run the
step once more with those FILE STATUS values injected on both sides at the same statement -- GnuCOBOL through
tests/equivalence/faults/ggfault.c (preloaded in front of libcob's file I/O), Java through the generated
CobolFiles, which a port calls once per I/O statement (the porting rules). A planned statement returns its status
instead of running. CALL 'CEE3ABD' is tests/equivalence/faults/ggabend.c, which records ABEND Unnnn; the Java
side's is CobolAbend. A run is proven when both sides abend with the same code, or neither does and RETURN-CODE and
every output are equal -- and, for a fault run, the same faults fired, at least one. `--faults all|none|NAME,...`;
the COBOL coverage (#4023) counts every run. A CICS case's scenario may carry `"faults"` too (READ conditions:
equivalence_cics.fault_lines).

#4048 follow-up -- entry runs: a batch case's `"entries"` ([{method, why}]) each run the step once more through
that no-argument method of the service (a controller's entry, executeX) instead of runBatch, compared with the
same COBOL run: the same abend, or the same RETURN-CODE -- the one an int method returns (#4342: the generated
executeX returns runBatch's), 0 for a void method that returns normally -- and every output equal. The evidence
record counts each as run by the proof (proof_reach).

A case with `"kind": "cics"` is an online program (#3754, equivalence_cics.py): its
EXEC CICS is translated to calls into a stub runtime, each scenario (COMMAREA, key
pressed, screen input) runs as one task on both sides -- the Java as a CicsTask through
the service's runTask -- and the tasks' events (SEND MAP, SEND TEXT, RETURN, XCTL, ABEND)
are compared field by field.

#4449 -- the java-facade side: a CICS case's port is proven through its deployed entry points too. The same project
runs every scenario once more, the task entered through the program's Spring facade -- handleTransaction, or
handleLink for a LINKed program (`"linked": true`), and a LINK target the case runs through its handleLink -- with
the scenario's region joined (CicsTask.join), so the facade's task IS the scenario's task. It is compared with the
same COBOL tasks, exactly as the runTask side is, and the case is proven only when both sides are (report
`facade`). `--no-facades` leaves it out (never with --record).
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cobol_coverage as cov  # noqa: E402 -- #4023

# The primitives every harness module shares live in a leaf module (no cycle); re-exported here.
import equivalence_db2
import equivalence_oracle
import equivalence_sql
from equivalence_common import (
    CASES,
    DEFAULT_DATA_ENCODING,
    IMAGE,
    _fixed,
    _input_path,
    compile_options,
    data_encoding,
    decode_field,
    diff_records,
    diff_varseq,
    java_failure_report,
    layout_fields,
    numproc_guard,
    read_program,
    stage_copybooks,
    require_ascii_runtime,
    reuse,
    reused,
    run_cobol_step,
    step_reused,
)


# ---- COBOL side ----------------------------------------------------------------------
def _cbl(lines: list[str]) -> str:
    """Fixed-format COBOL: each line in columns 8-72 (area A at 8)."""
    out = []
    for ln in lines:
        body = ln.rstrip()
        assert len(body) <= 65, f"COBOL line too long: {body!r}"
        out.append(" " * 7 + body)
    return "\n".join(out) + "\n"


def _keyed_fd(name: str, reclen: int, keys: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(SELECT lines, FD lines) of an indexed file keyed like the program's SELECT: one 01
    per key, each placing that key at its offset (the 01s implicitly redefine)."""
    sel = [f"    SELECT {name}-F ASSIGN TO {name}", "        ORGANIZATION IS INDEXED", "        ACCESS MODE IS DYNAMIC",
           f"        RECORD KEY IS {name}-K0"]  # fmt: skip
    for i, k in enumerate(keys[1:], 1):
        sel.append(f"        ALTERNATE RECORD KEY IS {name}-K{i}" + (" WITH DUPLICATES" if k.get("duplicates") else ""))
    sel[-1] += "."
    fd = [f"FD  {name}-F.", f"01  {name}-R PIC X({reclen})."]
    for i, k in enumerate(keys):
        fd.append(f"01  {name}-R{i}.")
        if k["offset"]:
            fd.append(f"    05 FILLER PIC X({k['offset']}).")
        fd.append(f"    05 {name}-K{i} PIC X({k['length']}).")
        rest = reclen - k["offset"] - k["length"]
        if rest:
            fd.append(f"    05 FILLER PIC X({rest}).")
    return sel, fd


def cobol_loader(name: str, reclen: int, keys: list[dict[str, Any]]) -> str:
    """Loads fixed-length records (file IN) into an indexed file keyed like the program's."""
    sel, fd = _keyed_fd(name, reclen, keys)
    return _cbl([
        "IDENTIFICATION DIVISION.", f"PROGRAM-ID. LD{name[:6]}.", "ENVIRONMENT DIVISION.", "INPUT-OUTPUT SECTION.",
        "FILE-CONTROL.", "    SELECT IN-F ASSIGN TO INFILE ORGANIZATION IS SEQUENTIAL.", *sel,
        "DATA DIVISION.", "FILE SECTION.", "FD  IN-F.", f"01  IN-R PIC X({reclen}).", *fd,
        "WORKING-STORAGE SECTION.", "01  EOF PIC X VALUE 'N'.",
        "PROCEDURE DIVISION.", f"    OPEN INPUT IN-F OUTPUT {name}-F",
        "    PERFORM UNTIL EOF = 'Y'", "        READ IN-F AT END MOVE 'Y' TO EOF",
        f"        NOT AT END WRITE {name}-R FROM IN-R", "          INVALID KEY DISPLAY 'DUPLICATE ' IN-R(1:40)",
        "          END-WRITE", "        END-READ", "    END-PERFORM", f"    CLOSE IN-F {name}-F", "    STOP RUN.",
    ])  # fmt: skip


def cobol_unloader(name: str, reclen: int, keys: list[dict[str, Any]]) -> str:
    """Unloads an indexed file, in primary-key order, to fixed-length records (file OUT)."""
    sel, fd = _keyed_fd(name, reclen, keys)
    return _cbl([
        "IDENTIFICATION DIVISION.", f"PROGRAM-ID. UL{name[:6]}.", "ENVIRONMENT DIVISION.", "INPUT-OUTPUT SECTION.",
        "FILE-CONTROL.", "    SELECT OUT-F ASSIGN TO OUTFILE ORGANIZATION IS SEQUENTIAL.", *sel,
        "DATA DIVISION.", "FILE SECTION.", "FD  OUT-F.", f"01  OUT-R PIC X({reclen}).", *fd,
        "WORKING-STORAGE SECTION.", "01  EOF PIC X VALUE 'N'.",
        "PROCEDURE DIVISION.", f"    OPEN INPUT {name}-F OUTPUT OUT-F",
        "    PERFORM UNTIL EOF = 'Y'", f"        READ {name}-F NEXT AT END MOVE 'Y' TO EOF",
        f"        NOT AT END WRITE OUT-R FROM {name}-R", "        END-READ", "    END-PERFORM",
        f"    CLOSE {name}-F OUT-F", "    STOP RUN.",
    ])  # fmt: skip


def cobol_driver(program: str, parm: Optional[str]) -> str:
    """Runs `program` as the JCL step does: the PARM in a halfword-length-prefixed LINKAGE area."""
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. EQDRIVER.", "DATA DIVISION.", "WORKING-STORAGE SECTION."]
    if parm is not None:
        lines += ["01  JCL-PARM.", f"    05 PARM-LEN PIC S9(4) COMP VALUE {len(parm)}.",
                  f"    05 PARM-TEXT PIC X({max(len(parm), 1)}) VALUE '{parm}'."]  # fmt: skip
    lines += ["PROCEDURE DIVISION.", f"    CALL '{program}'" + (" USING JCL-PARM" if parm is not None else ""),
              "    STOP RUN."]  # fmt: skip
    return _cbl(lines)


FAULTS_DIR = CASES / "faults"  # the fault injector and the abend stub (ggfault.c, ggabend.c)
LE_MODELS = CASES / "le"  # models of the routines a program CALLs that GnuCOBOL has no code for (CEEDAYS, COBDATFT)
# A model refuses what it does not model ("NAME: ... is not modelled" on stderr, exit 98): never the oracle.
MODEL_REFUSAL = re.compile(rb"^([A-Z0-9]{1,8}): [^\n]* is not modelled$", re.M)
FAULT_OPS = ("OPEN", "CLOSE", "READ", "WRITE", "REWRITE", "DELETE", "START")


def fault_plan(fault: dict[str, Any]) -> str:
    """A case fault's plan as both sides read it: `DD OP NTH STATUS` per line (see faults/ggfault.c)."""
    lines = []
    for f in fault.get("plan", []):
        if f["op"] not in FAULT_OPS or not re.fullmatch(r"[0-9A-Z]{2}", str(f["status"])):
            raise ValueError(f"fault {fault['name']}: bad op / status {f}")
        nth = "*" if f.get("nth", 1) == "*" else int(f.get("nth", 1))
        lines.append(f"{f['dd']} {f['op']} {nth} {f['status']}")
    return "\n".join(lines) + "\n"


def run_cobol(
    case: dict[str, Any], corpus: Path, work: Path, fault: Optional[dict[str, Any]] = None
) -> dict[str, bytes]:
    """Stage, compile and run the case's program under GnuCOBOL; {dd: output bytes}, plus RETURN-CODE -- or,
    when the step abended, ABEND (Unnnn, the CEE3ABD stub's) -- and, for a `fault` run, FAULTS: the planned
    faults that fired (#4023 follow-up; the plan is injected by faults/ggfault.c)."""
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    # #3828: the program's CBL / PROCESS cards and the case's `compiler_options` become cobc flags
    require_ascii_runtime(case)  # #3815: an EBCDIC data page cannot run under GnuCOBOL
    enc = data_encoding(case)
    # #3815: read by the engine's ladder (or the declared page), staged in the encoding it was read in
    source, staged = read_program(case, corpus / case["program_source"])
    program, option_flags = compile_options(case, source)
    db2 = case.get("db2")
    if db2:  # a Db2 program: its EXEC SQL precompiled into calls of the SQL stub (equivalence_sql.py)
        dirs = [corpus / d for d in [*case.get("copy_dirs", []), *db2.get("include_dirs", [])]]
        try:
            program, table = equivalence_sql.precompile(
                program, dirs, corpus / case["program_source"], program=case["program"]
            )
        except equivalence_sql.Unsupported as e:
            raise RuntimeError(f"not runnable faithfully: {e}") from e
        (work / "stmts.txt").write_text(table, encoding="latin-1")
        shutil.copy(equivalence_db2.STUB, src / "ggsql.c")
    (src / "PROGRAM.cbl").write_text(program, encoding=staged)
    stage_copybooks(case, corpus, src)
    script = ["set -e", "cd /work"]
    flags = " ".join(["-std=ibm -fsign=EBCDIC", *option_flags, "-I /work/src"])
    import equivalence_inputs  # #3804: `@generate` inputs, from their record layouts

    generated = equivalence_inputs.generate_inputs(case, corpus)
    for dd, spec in case["datasets"].items():
        if dd in generated:
            (work / f"{dd}.in").write_bytes(generated[dd])
        elif "input" in spec:
            (work / f"{dd}.in").write_bytes(_fixed(_input_path(case, corpus, spec["input"]), spec["reclen"], enc))
        if spec.get("organization") == "indexed":
            (src / f"LD{dd}.cbl").write_text(cobol_loader(dd, spec["reclen"], spec["keys"]), encoding="ascii")
            (src / f"UL{dd}.cbl").write_text(cobol_unloader(dd, spec["reclen"], spec["keys"]), encoding="ascii")
            script += [f"cobc -x {flags} -o ld{dd} src/LD{dd}.cbl", f"cobc -x {flags} -o ul{dd} src/UL{dd}.cbl"]
            if "input" in spec:
                script.append(f"INFILE=/work/{dd}.in {dd}=/work/{dd}.idx ./ld{dd}")
        elif "input" in spec:
            script.append(f"cp /work/{dd}.in /work/{dd}.idx")
    (src / "EQDRIVER.cbl").write_text(cobol_driver(case["program"], case.get("parm")), encoding="ascii")
    for stub in ("ggabend.c", "ggfault.c", "ggdisplay.c"):
        shutil.copy(FAULTS_DIR / stub, src / stub)
    models = sorted(LE_MODELS.glob("*.c"))
    for m in models:
        shutil.copy(m, src / m.name)
    # #4023: traced; CEE3ABD is the abend stub, which records the abend instead of failing the CALL
    sql = f" src/ggsql.c {equivalence_db2.COBOL_LINK}" if db2 else ""
    le = "".join(f" src/{m.name}" for m in models)
    script.append(
        f"cobc -x {flags} {cov.TRACE_FLAG} -o program src/EQDRIVER.cbl src/PROGRAM.cbl src/ggabend.c{le}{sql}"
    )
    # #4056: DISPLAY as IBM writes it (faults/ggdisplay.c), so SYSOUT is compared against IBM's text
    script.append("gcc -shared -fPIC -O2 -o /work/ggdisplay.so src/ggdisplay.c -ldl")
    inject = "LD_PRELOAD=/work/ggdisplay.so "
    if fault is not None:
        (work / "fault.plan").write_text(fault_plan(fault), encoding="ascii")
        script.append("gcc -shared -fPIC -O2 -o /work/ggfault.so src/ggfault.c -ldl")
        inject = (
            "GGFAULT_PLAN=/work/fault.plan GGFAULT_LOG=/work/FAULTS LD_PRELOAD='/work/ggfault.so /work/ggdisplay.so' "
        )
    env = " ".join(f"{dd}=/work/{dd}.idx" for dd in case["datasets"])
    clock = f"COB_CURRENT_DATE='{case['clock']}' " if case.get("clock") else ""
    tz = f"TZ='{case['zone']}' " if case.get("zone") else ""
    # the step's RETURN-CODE is an output like any other (CBTRN02C sets 4 when it rejects): recorded, not fatal
    sqlenv = equivalence_db2.cobol_env("/work/stmts.txt") if db2 else ""
    if db2:  # #4173: each statement the step runs traced; a fault run's SQL faults, those that fire logged
        sqlenv += "GGSQL_TRACE=/work/sqltrace.txt GGSQL_FAULTS_LOG=/work/FAULTS "
        (work / "sqltrace.txt").unlink(missing_ok=True)
        if fault is not None and fault.get("sql_plan"):
            (work / "sqlfaults.cfg").write_text("".join(x + "\n" for x in fault["sql_plan"]), encoding="ascii")
            sqlenv += "GGSQL_FAULTS=/work/sqlfaults.cfg "
    script.append(f"set +e; {cov.trace_env('/work/' + cov.TRACE_NAME)}GG_ABEND=/work/ABEND COB_VARSEQ_FORMAT=0 {inject}{tz}{clock}{env} "
                  f"{sqlenv}./program > /work/stdout.txt 2>&1; echo $? > /work/RETURN-CODE; set -e")  # fmt: skip
    # after an abend (or an OPEN a fault refused) an output may not exist: unloaded if it does
    for dd, spec in case["datasets"].items():
        if spec.get("compare") and spec.get("organization") == "indexed":
            script.append(f"[ ! -e /work/{dd}.idx ] || {dd}=/work/{dd}.idx OUTFILE=/work/{dd}.out ./ul{dd} || true")
        elif spec.get("compare"):
            script.append(f"[ ! -e /work/{dd}.idx ] || cp /work/{dd}.idx /work/{dd}.out")
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    if db2 and not step_reused(work):
        equivalence_db2.reset(case, corpus)
    proc = (run_cobol_step(work, equivalence_db2.COBOL_IMAGE, tuple(equivalence_db2.cobol_docker_args(case))) if db2
            else run_cobol_step(work))  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"COBOL side failed:\n{proc.stdout}\n{proc.stderr}")
    outs = {dd: (work / f"{dd}.out").read_bytes() for dd, spec in case["datasets"].items()
            if spec.get("compare") and (work / f"{dd}.out").is_file()}  # fmt: skip
    if db2:  # what the run left in the tables (kept with the run, for --reuse)
        saved = work / "db2"
        if not proc.args or proc.args[0] != "reuse":
            saved.mkdir(exist_ok=True)
            for key, data in equivalence_db2.outputs(case).items():
                (saved / key.replace(" ", "_")).write_bytes(data)
        for t in db2.get("compare", []):
            f = saved / f"DB2_{t}"
            outs[f"DB2 {t}"] = f.read_bytes() if f.is_file() else b""
    outs["SYSOUT"] = (work / "stdout.txt").read_bytes() if (work / "stdout.txt").is_file() else b""  # #4056
    # A CALL to a routine nothing here provides (CBACT01C's assembler COBDATFT) ends the run in libcob's own
    # "module not found": that is GnuCOBOL's failure, never the program's behaviour -- refused, not recorded as the
    # oracle (SYSOUT leaves libcob's lines out, so a port imitating the crash would otherwise prove).
    refused = MODEL_REFUSAL.search(outs["SYSOUT"])
    if refused:  # a model of a CALLed routine reached what it does not model: no oracle for this run
        raise RuntimeError(f"the run reaches what the {refused.group(1).decode()} model does not model "
                           f"({refused.group(0).decode()}) -- not runnable faithfully")  # fmt: skip
    missing = re.search(rb"libcob: [^\n]*module '([^']+)' not found", outs["SYSOUT"])
    if missing:
        raise RuntimeError(f"the program CALLs {missing.group(1).decode()!r}, which no model provides "
                           "(GnuCOBOL: module not found) -- not runnable faithfully")  # fmt: skip
    abend = work / "ABEND"
    if abend.is_file():
        outs["ABEND"] = abend.read_bytes().strip()
    else:
        outs["RETURN-CODE"] = (work / "RETURN-CODE").read_text(encoding="ascii").strip().encode()
    if fault is not None:
        fired = work / "FAULTS"
        outs["FAULTS"] = fired.read_bytes() if fired.is_file() else b""
    return outs


def cobol_coverage(case: dict[str, Any], corpus: Path, traces: list[Path], out: Path) -> Optional[dict[str, Any]]:
    """#4023: how much of the program the runs execute together (the normal run and every fault run)."""
    source, staged = read_program(case, corpus / case["program_source"])
    program, _flags = compile_options(case, source)
    staged_file = traces[0].parent / "src" / "PROGRAM.cbl" if traces else None
    if case.get("db2") and staged_file is not None and staged_file.is_file():  # what ran: the precompiled text
        program = staged_file.read_text(encoding=staged)
    return cov.write_run_coverage(out, source=corpus / case["program_source"], original=source, compiled=program,
                                  traces=[t for t in traces if t.is_file()], compiled_name="PROGRAM.cbl",
                                  copybooks=corpus, encoding=staged)  # fmt: skip


PREBUILT_ENV = "GITGALAXY_ORACLE_PREBUILT"


def build_image() -> None:
    """Build the oracle image -- unless CI says it loaded it from its cache (GITGALAXY_ORACLE_PREBUILT=1) and it is
    there: the fingerprint check (equivalence_oracle.py --strict) is what vouches it is the pinned oracle."""
    if os.environ.get(PREBUILT_ENV) == "1" and subprocess.run(
        ["docker", "image", "inspect", IMAGE], capture_output=True, check=False  # noqa: S603, S607
    ).returncode == 0:  # fmt: skip
        return
    subprocess.run(
        ["docker", "build", "-q", "-t", IMAGE, "-f", str(CASES / "gnucobol.Dockerfile"), str(CASES)],
        check=True, capture_output=True,
    )  # fmt: skip


def report_markdown(case: dict[str, Any], report: dict[str, Any]) -> str:
    """The run as Markdown: per output, records equal / total and every differing field."""
    lines = [f"# {case['program']} -- COBOL vs Java ({report['java']})", "",
             f"Case `{case['name']}`: {case['corpus']} `{case['program_source']}`, job {case.get('job')} step "
             f"{case.get('step')}, PARM `{case.get('parm')}`, clock `{case.get('clock')}`.", "",
             f"RETURN-CODE: COBOL `{report.get('return_code', {}).get('cobol')}`, Java "
             f"`{report.get('return_code', {}).get('java')}`.", "",
             f"Key order covered: {report.get('collation', COLLATION)}.", "",
             "| output | records equal | total | FILLER differs (not compared) |", "|---|---|---|---|"]  # fmt: skip
    for dd, d in report["outputs"].items():
        lines.append(f"| {dd} | {d['equal']} | {d['records']} | {d.get('filler_differs', 0)} |")
    if report.get("environments"):  # #3821
        lines += ["", "| JVM environment | locale | time zone | equal to COBOL |", "|---|---|---|---|"]
        for e in report["environments"]:
            lines.append(f"| {e['name']} | {e['locale']} | {e['tz']} | {'yes' if e['ok'] else '**no**'} |")
    if report.get("abend") and (report["abend"]["cobol"] or report["abend"]["java"]):
        lines += ["", f"ABEND: COBOL `{report['abend']['cobol']}`, Java `{report['abend']['java']}`."]
    if report.get("faults"):  # #4023 follow-up
        lines += ["", "## Fault runs", "",
                  ("Each run injects file statuses on both sides at the same statement (tests/equivalence/faults/"
                   "ggfault.c for GnuCOBOL, the generated CobolFiles for Java) and is proven like the normal run: "
                   "the same abend, or the same RETURN-CODE and outputs, and the same faults fired."), "",
                  "| fault | plan (DD OP NTH STATUS) | why | outcome | equal |", "|---|---|---|---|---|"]  # fmt: skip
        for f in report["faults"]:
            lines.append(f"| {f['name']} | {'; '.join(f'`{x}`' for x in f['plan'])} | {f['why']} | {f['summary']} | "
                         f"{'yes' if f['ok'] else '**no**'} |")  # fmt: skip
    if report.get("entries"):  # #4048 follow-up
        lines += ["", "## Entry runs", "",
                  ("Each runs the step once more through a no-argument method of the service instead of runBatch, "
                   "and is proven against the same COBOL run: the same abend, or RETURN-CODE 0 (the method returns "
                   "none) and the same outputs."), "",
                  "| method | why | outcome | equal |", "|---|---|---|---|"]  # fmt: skip
        for e in report["entries"]:
            lines.append(f"| `{e['method']}()` | {e['why']} | {e['summary']} | {'yes' if e['ok'] else '**no**'} |")
    lines += cov.report_lines(report.get("coverage"), report.get("runs", 1), report.get("proven", False))  # #4023
    for dd, d in report["outputs"].items():
        if d["diffs"]:
            lines += ["", f"## {dd}: differences", "", "| record | field | COBOL | Java |", "|---|---|---|---|"]
            for x in d["diffs"][:200]:
                if x.get("missing"):
                    lines.append(f"| {x['record']} | (record) | {'-' if x['missing'] == 'cobol' else 'present'} | "
                                 f"{'-' if x['missing'] == 'java' else 'present'} |")  # fmt: skip
                for fd in x.get("fields", []):
                    kind = " (bytes; same value)" if fd.get("raw") else ""
                    lines.append(f"| {x['record']} | {fd['field']}{kind} | `{fd['cobol']}` | `{fd['java']}` |")
    return "\n".join(lines) + "\n"


# #3821: what a KSDS browse or a sorted output was compared in -- both sides here, not the mainframe's
# EBCDIC order (#3834 adds that dimension). A claim holds for the order it was made in.
COLLATION = "ASCII / ISO-8859-1 byte order on both sides (GnuCOBOL BDB, H2), not the mainframe's EBCDIC order"


def _environments(arg: Optional[str], case: dict[str, Any]) -> list[dict[str, str]]:
    """#3821: `--environments a,b` / `all`, else the case's own list, else the pinned default."""
    import equivalence_java as ej

    names = (arg.split(",") if arg and arg != "all" else list(ej.ENVIRONMENTS) if arg == "all"
             else case.get("environments") or ["default"])  # fmt: skip
    return [ej.environment(n.strip()) for n in names if n.strip()]


# ---- the porting loop's feedback (port_runner run --feedback) -------------------------------
def _run_feedback(title: str, run: dict[str, Any], limit: int = 5) -> list[str]:
    """What one run found, for the next porting attempt: its outcome, and per differing output the first
    records that differ, field by field (COBOL value vs the port's)."""
    out = [f"### {title}: {run.get('summary') or 'differs'}", ""]
    for dd, d in (run.get("outputs") or {}).items():
        if not d["diffs"]:
            continue
        out.append(f"{dd}: {d['equal']}/{d['records']} records equal. First differences:")
        for x in d["diffs"][:limit]:
            if x.get("missing"):
                out.append(
                    f"- record {x['record']}: missing on the {'COBOL' if x['missing'] == 'cobol' else 'Java'} side"
                )
            for fd in x.get("fields", [])[:8]:
                out.append(f"- record {x['record']} {fd['field']}: COBOL `{fd['cobol']}`, Java `{fd['java']}`")
        out.append("")
    s = run.get("sysout") or {}
    if s.get("compared") and s.get("diffs"):  # #4056: what the program DISPLAYs, line by line
        out.append(f"SYSOUT (DISPLAY output): {s['equal']}/{s['lines']} lines equal. First differences:")
        for x in s["diffs"][:limit]:
            out.append(f"- line {x['line']}: COBOL `{x['cobol']}`, Java `{x['java']}`")
        out.append("")
    return out


def feedback_md(report: dict[str, Any]) -> str:
    """#4023 follow-up: the proof's findings as port_runner's `--feedback` hands them to the next attempt --
    every run that is not equal (the normal run, each JVM environment, each fault run with its plan and why)."""
    out: list[str] = []
    first = {"summary": None, "outputs": report.get("outputs", {}), "sysout": report.get("sysout")}
    rc, ab = report.get("return_code") or {}, report.get("abend") or {}
    why = []
    if ab.get("cobol") or ab.get("java"):
        if ab.get("cobol") != ab.get("java"):
            why.append(f"ABEND: COBOL {ab.get('cobol')}, Java {ab.get('java')}")
    elif rc.get("cobol") != rc.get("java"):
        why.append(f"RETURN-CODE: COBOL {rc.get('cobol')}, Java {rc.get('java')}")
    why += [f"{dd}: {d['equal']}/{d['records']} records equal" for dd, d in first["outputs"].items() if d["diffs"]]
    s = report.get("sysout") or {}
    if s.get("compared") and s.get("diffs"):
        why.append(f"SYSOUT: {s['equal']}/{s['lines']} lines equal")
    if why:
        first["summary"] = "; ".join(why)
        out += _run_feedback("The normal run (the case's own inputs)", first)
    for e in report.get("environments", [])[1:]:
        if not e.get("ok"):
            out += [f"### JVM environment {e['name']} ({e['locale']}, {e['tz']}): differs from the COBOL", ""]
    for f in report.get("faults", []):
        if not f["ok"]:
            out += [f"The fault run `{f['name']}` injects {'; '.join(f['plan'])} (DD OP NTH FILE-STATUS) on both "
                    f"sides -- {f.get('why', '')}", ""]  # fmt: skip
            out += _run_feedback(f"Fault run {f['name']}", f)
    for e in report.get("entries", []):
        if not e["ok"]:
            out += [f"The entry run `{e['method']}()` runs the step through that method -- {e.get('why', '')}", ""]
            out += _run_feedback(f"Entry run {e['method']}", e)
    return "\n".join(out).strip()


# ---- #4023 follow-up: fault runs ------------------------------------------------------
def enumerated_batch_sql_faults(cobol_work: Path, table: str) -> list[dict[str, Any]]:
    """#4173: one more run of a batch step per SQL statement its normal run executed, that statement's first
    execution failing (equivalence_cics.default_fault's SQLCODE) -- a fault run like the case's own."""
    import equivalence_cics as ec

    stmts = {(x["program"], x["line"]): x for x in ec.sql_statements(table)}
    trace = cobol_work / "sqltrace.txt"
    words = trace.read_text(encoding="ascii").split() if trace.is_file() else []
    out, seen = [], set()
    for prog, line in zip(words[::2], words[1::2]):
        key = (prog, int(line))
        if key in seen or key not in stmts:
            continue
        seen.add(key)
        code = ec.default_fault(stmts[key])
        if code is None:
            continue
        out.append({"name": f"sql-{prog.lower()}-{line}", "plan": [], "derived": True,
                    "sql_plan": [f"{prog} {line} 1 {code} {ec.SQLSTATES[code]}"],
                    "why": f"#4173: the first {stmts[key]['kind']} at {prog} line {line} failing (SQLCODE {code})"})  # fmt: skip
    return out


def selected_faults(case: dict[str, Any], arg: Optional[str]) -> list[dict[str, Any]]:
    """The case's `faults` to run: `all` (the default), `none`, or names separated by commas."""
    faults = case.get("faults", [])
    if arg in (None, "all"):
        return faults
    if arg == "none":
        return []
    names = [n.strip() for n in arg.split(",") if n.strip()]
    unknown = sorted(set(names) - {f["name"] for f in faults})
    if unknown:
        raise SystemExit(f"{case['name']}: no fault named {unknown} (the case has {[f['name'] for f in faults]})")
    return [f for f in faults if f["name"] in names]


POSITIVE_OVERPUNCH = b"{ABCDEFGHI"  # a positive zoned sign digit 0-9 (C zone), as the ASCII data writes it


def accept_unsigned_positive(a: bytes, b: bytes) -> tuple[bytes, bytes, int]:
    """oracle_assumptions.md C10, for the datasets a case names in `"zoned_sign_equivalent"`: a byte that is a
    plain digit on one side and the same digit with the positive overpunch on the other (an F zone against a C
    zone: the same positive value; GnuCOBOL's INITIALIZE / VALUE ZERO leave the F, z/OS writes the preferred C)
    is taken as equal. Both are made the overpunch; the count of such bytes is reported, never hidden."""
    if len(a) != len(b):
        return a, b, 0
    x, y, n = bytearray(a), bytearray(b), 0
    for i, (p, q) in enumerate(zip(a, b)):
        if p != q:
            for digit, over in ((p, q), (q, p)):
                if 0x30 <= digit <= 0x39 and over == POSITIVE_OVERPUNCH[digit - 0x30]:
                    x[i] = y[i] = over
                    n += 1
                    break
    return bytes(x), bytes(y), n


def compare_run(case: dict[str, Any], corpus: Path, cobol: dict[str, bytes], java: dict[str, bytes],
                fault: Optional[dict[str, Any]] = None) -> dict[str, Any]:  # fmt: skip
    """One run of the step on both sides: equal when both abend with the same code, or neither does and their
    RETURN-CODE and every compared output are equal. A fault run also needs the same faults fired on both
    sides, and at least one: a planned fault the run never reaches tested nothing. After an abend the outputs
    are not compared -- what an abended step leaves in its datasets is not defined."""
    abend = {"cobol": cobol.get("ABEND", b"").decode() or None, "java": java.get("ABEND", b"").decode() or None}
    rc = {"cobol": cobol.get("RETURN-CODE", b"").decode(), "java": java.get("RETURN-CODE", b"").decode()}
    run: dict[str, Any] = {"abend": abend, "return_code": rc, "outputs": {}}
    why: list[str] = []
    if fault is not None:
        fired = {side: sorted(res.get("FAULTS", b"").decode().split("\n")) for side, res in
                 (("cobol", cobol), ("java", java))}  # fmt: skip
        fired = {side: [x for x in lines if x.strip()] for side, lines in fired.items()}
        run["fired"] = fired
        if not fired["cobol"]:
            why.append("the planned fault never fired on the COBOL side: the run does not reach it")
        if fired["cobol"] != fired["java"]:
            why.append(f"faults fired differ: COBOL {fired['cobol']}, Java {fired['java']}")
    if abend["cobol"] or abend["java"]:
        if abend["cobol"] != abend["java"]:
            why.append(f"ABEND: COBOL {abend['cobol']}, Java {abend['java']}")
    else:
        if rc["cobol"] != rc["java"]:
            why.append(f"RETURN-CODE: COBOL {rc['cobol']}, Java {rc['java']}")
        for dd, spec in case["datasets"].items():
            if not spec.get("compare"):
                continue
            left, right = cobol.get(dd, b""), java.get(dd, b"")
            if dd in case.get("zoned_sign_equivalent", []):  # C10, declared by the case
                left, right, n = accept_unsigned_positive(left, right)
                if n:
                    run.setdefault("sign_equivalent", {})[dd] = n
            if spec.get("record_format") == "V":  # variable-length: each record against its length's layout
                layouts = {int(n): layout_fields(corpus, spec["copybook"], rec) for n, rec in spec["layouts"].items()}
                d = diff_varseq(left, right, layouts, case.get("code_page", "cp037"),
                                data_encoding(case))  # fmt: skip
                run["outputs"][dd] = d
                if d["equal"] != d["records"] or d["diffs"]:
                    why.append(f"{dd}: {d['equal']}/{d['records']} records equal")
                continue
            fields = layout_fields(corpus, spec["copybook"], spec.get("record"))
            d = diff_records(left, right, spec["reclen"], fields, case.get("code_page", "cp037"),
                             data_encoding(case))  # fmt: skip
            if d["layout_bytes"] != spec["reclen"]:  # #3820: the copybook's layout does not fill the record
                print(f"{case['program']} {dd}: layout is {d['layout_bytes']} bytes, reclen {spec['reclen']}")
            run["outputs"][dd] = d
            if d["equal"] != d["records"] or d["diffs"]:
                why.append(f"{dd}: {d['equal']}/{d['records']} records equal")
        for t in (case.get("db2") or {}).get("compare", []):  # a Db2 table: its rows, as text, line by line
            d = equivalence_db2.diff_dump(cobol.get(f"DB2 {t}", b""), java.get(f"DB2 {t}", b""))
            run["outputs"][f"DB2 {t}"] = d
            diffs, rows = d["diffs"], d["records"]
            if diffs:
                why.append(f"DB2 {t}: {rows - len(diffs)}/{rows} rows equal")
    if case.get("sysout", True):  # #4056: the job log too, after an abend as well (its messages say why)
        s = compare_sysout(cobol.get("SYSOUT", b""), java.get("SYSOUT", b""), data_encoding(case))
        run["sysout"] = s
        if s["compared"] and s["diffs"]:
            why.append(f"SYSOUT: {s['equal']}/{s['lines']} lines equal")
    run["ok"] = not why
    ends = (f"both ABEND {abend['cobol']}" if abend["cobol"] and abend["cobol"] == abend["java"]
            else f"both end RETURN-CODE {rc['cobol']}" if not why else "")  # fmt: skip
    run["summary"] = "; ".join(why) if why else ends
    if run.get("sign_equivalent"):
        run["summary"] += " (C10: " + ", ".join(f"{dd} {n} sign bytes F/C" for dd, n in run["sign_equivalent"].items())
        run["summary"] += ")"
    return run


NOT_MODELLED = "GGDISPLAY-NOT-MODELLED"  # faults/ggdisplay.c: an operand IBM's text is not modelled for


def sysout_lines(data: bytes, enc: str) -> list[str]:
    """The job log's lines as compared: trailing blanks dropped (a SYSOUT record is blank-padded to its length,
    so they are not text) and libcob's own runtime messages left out (they are GnuCOBOL's, not the program's)."""
    lines = [x.rstrip(" \r") for x in data.decode(enc).split("\n") if not x.startswith("libcob: ")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def compare_sysout(cobol: bytes, java: bytes, enc: str) -> dict[str, Any]:
    """#4056: what each side DISPLAYed, line by line. Not compared (and said so) when the COBOL side DISPLAYed an
    operand ggdisplay.c does not model: GnuCOBOL's text for it is not IBM's."""
    c, j = sysout_lines(cobol, enc), java.decode("utf-8").split("\n") if java else []
    j = [x.rstrip(" \r") for x in j]
    while j and not j[-1]:
        j.pop()
    if NOT_MODELLED in c:
        return {"compared": False, "why": "a DISPLAY operand IBM's text is not modelled for (faults/ggdisplay.c)",
                "lines": len(c), "equal": 0, "diffs": []}  # fmt: skip
    diffs = [{"line": i + 1, "cobol": c[i] if i < len(c) else None, "java": j[i] if i < len(j) else None}
             for i in range(max(len(c), len(j))) if (c[i] if i < len(c) else None) != (j[i] if i < len(j) else None)]  # fmt: skip
    return {"compared": True, "lines": len(c), "equal": max(len(c), len(j)) - len(diffs), "diffs": diffs[:20],
            "differing": len(diffs)}  # fmt: skip


# ---- CLI -----------------------------------------------------------------------------
def load_case(name: str, case_file: Optional[Path] = None) -> dict[str, Any]:
    """The case `name`, from its case.json -- or from `case_file` (#4049: a candidate the test-strengthening loop
    wrote), with the case's own directory still the home of its inputs and its port."""
    case = json.loads((case_file or CASES / name / "case.json").read_text(encoding="utf-8"))
    case["name"] = name
    return case


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--keep", type=Path, help="work directory to keep (default: a temporary one)")
    r.add_argument("--cobol-only", action="store_true", help="run the COBOL side and print its outputs' shape")
    r.add_argument(
        "--port",
        type=Path,
        help="a port directory to prove instead of the case's own (laid out under com/gitgalaxy/modernized)",
    )
    r.add_argument("--environments", help="#3821: JVM environments to run the Java side under: NAME,NAME | "
                   "all | LOCALE/TZ (default: the case's `environments`, else `default`)")  # fmt: skip
    r.add_argument("--source-encoding", help="#3815: the COBOL sources' code page (default: the case's "
                   "`source_encoding`, else the engine's read_source ladder: BOM, UTF-8, cp1252, Latin-1)")  # fmt: skip
    r.add_argument("--data-encoding", help="#3815: the record bytes' code page, e.g. cp277, utf-8 (default: "
                   "the case's `data_encoding`, else latin-1)")  # fmt: skip
    r.add_argument("--faults", help="#4023 follow-up: the case's fault runs to run as well: all (default) | none | "
                   "NAME,NAME")  # fmt: skip
    r.add_argument("--sql-faults", default="auto", choices=("auto", "declared", "none"),
                   help="#4173: a Db2 case's SQL faults: auto (default: one more run per SQL statement the case "
                   "executes, it failing) | declared (the case's own sql_faults only) | none")  # fmt: skip
    r.add_argument("--case-file", type=Path, help="#4049: prove this case.json instead of the case's own (its "
                   "inputs and port still come from the case's directory)")  # fmt: skip
    r.add_argument("--reuse", type=Path, help="an earlier run's --keep directory of this case: its COBOL side "
                   "(each step whose run.sh is identical) and its generated project, re-overlaid with the port "
                   "(mutation testing: many ports of one case)")  # fmt: skip
    r.add_argument("--first-difference", action="store_true", help="stop at the first run that differs: the "
                   "verdict is the same, the report names only that run (mutation testing)")  # fmt: skip
    r.add_argument("--generated-only", action="store_true",
                   help="run the generated service as generated (no port): the generator's own baseline")  # fmt: skip
    r.add_argument("--no-facades", action="store_true", help="#4449: a CICS case's port is proven through runTask "
                   "only, without the java-facade side (every scenario again through the program's deployed entry "
                   "point: handleTransaction / handleLink)")  # fmt: skip
    r.add_argument("--record", action="store_true", help="#4048: write the case's evidence record "
                   "(tests/equivalence/CASE/evidence.json) from this run -- the committed port on the committed case "
                   "only")  # fmt: skip
    sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "list":
        for p in sorted(CASES.glob("*/case.json")):
            print(p.parent.name)
        return 0
    import mainframe_corpus as mc

    if args.record and (args.port or args.case_file or args.reuse or args.first_difference or args.generated_only
                        or args.cobol_only or args.faults not in (None, "all") or args.environments
                        or args.sql_faults != "auto" or args.source_encoding or args.data_encoding
                        or args.no_facades):  # fmt: skip
        raise SystemExit(
            "--record proves the committed port on the committed case as it is: drop --port / "
            "--case-file / --reuse / --first-difference / --generated-only / --cobol-only / --no-facades "
            "and the overrides"
        )
    case = load_case(args.case, args.case_file)
    for key in ("source_encoding", "data_encoding"):  # #3815: the CLI overrides the case
        if getattr(args, key):
            case[key] = getattr(args, key)
    data_encoding(case)  # a bad declaration fails here, not after the COBOL build
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    if not args.cobol_only:  # #4271: NUMPROC(PFD) only through a det port's guard (register C5)
        port_dir = None if args.generated_only else args.port or CASES / case.get("port_from", case["name"]) / "port"
        numproc_guard(case, read_program(case, corpus / case["program_source"])[0], port_dir)
    if case.get("db2"):  # a database of the pool to this case alone (parallel runs take the others, or wait)
        equivalence_db2.hold_lock()
    work = args.keep or Path(tempfile.mkdtemp(prefix=f"equiv_{args.case}_"))
    if args.reuse:
        reuse(work, args.reuse)
        equivalence_oracle.adopt_from(case, args.reuse)  # #4309: the COBOL outputs, and so the oracle, are EARLIER's
    else:
        build_image()
    if case.get("kind") == "call":  # #4023 follow-up: a CALLed subprogram, driven through its USING items
        import equivalence_call as ecall

        return _recorded(args, work, ecall.run_case(case, corpus, work, port=not args.generated_only,
                                                    port_dir=args.port, cobol_only=args.cobol_only))  # fmt: skip
    if case.get("kind") == "cics":  # #3754: an online program, run as tasks under the stub CICS runtime
        import equivalence_cics as ec

        return _recorded(args, work, ec.run_case(case, corpus, work, port=not args.generated_only,
                                                 port_dir=args.port, cobol_only=args.cobol_only,
                                                 sql_faults=args.sql_faults,
                                                 facades=not args.no_facades))  # fmt: skip
    faults = selected_faults(case, args.faults)
    if case.get("db2"):  # the case's tables, created from its DDL on the harness's Db2 (equivalence_db2.py)
        equivalence_db2.create(case, corpus)
    cobol = run_cobol(case, corpus, work / "cobol")
    if case.get("db2") and args.sql_faults != "none":  # #4173: the case's SQL faults, resolved to their statements
        import equivalence_cics as ec

        table = (work / "cobol" / "stmts.txt").read_text(encoding="latin-1")
        for f in faults:
            if f.get("sql_faults"):
                f["sql_plan"] = ec.sql_fault_plan(case, {"name": f["name"], **f}, table)
        if args.sql_faults == "auto" and args.faults != "none":
            faults = [*faults, *enumerated_batch_sql_faults(work / "cobol", table)]
    cobol_faults = {f["name"]: run_cobol(case, corpus, work / "faults" / f["name"] / "cobol", f) for f in faults}
    if args.cobol_only:
        for name, res in [("", cobol), *cobol_faults.items()]:
            for dd, data in res.items():
                if dd in ("RETURN-CODE", "ABEND", "FAULTS"):
                    what = data.decode().strip() or "(none)"
                elif dd in case["datasets"]:
                    what = f"{len(data)} bytes, {len(data) // case['datasets'][dd]['reclen']} records"
                else:  # SYSOUT (#4056): lines, not records
                    lines = data.count(b"\n")  # (no backslash inside an f-string: Python < 3.12)
                    what = f"{len(data)} bytes, {lines} lines"
                print(f"{'fault ' + name + ' ' if name else ''}{dd}: {what}")
        return 0
    import equivalence_java as ej

    envs = _environments(args.environments, case)
    by_name = {f"fault:{f['name']}": f for f in faults}
    entries = ej.entry_names(case)  # #4048 follow-up: the step once more through each entry method

    def differs(name: str, java: dict[str, bytes]) -> bool:
        f = by_name.get(name)
        return not compare_run(case, corpus, cobol_faults[f["name"]] if f else cobol, java, fault=f)["ok"]

    try:
        runs = ej.run_java_environments(case, corpus, work / "java", work / "cobol", envs,
                                        port=not args.generated_only, port_dir=args.port,
                                        faults=tuple((f["name"], fault_plan(f), "\n".join(f.get("sql_plan", [])))
                                                     for f in faults),
                                        stop=differs if args.first_difference else None,
                                        entries=tuple(entries))  # fmt: skip
    except RuntimeError as e:  # the port does not compile, or its run fails: the loop's feedback, not a crash
        failed = java_failure_report(case, work, str(e))
        (work / "report.json").write_text(json.dumps(failed, indent=2) + "\n", encoding="utf-8")
        print(f"{case['program']}: the Java side failed -- see {work / 'report.json'}")
        return _recorded(args, work, 1)
    report: dict[str, Any] = {"case": args.case, "program": case["program"], "outputs": {},
                              "java": "generated" if args.generated_only else "ported", "collation": COLLATION,
                              "port": str(args.port) if args.port else f"tests/equivalence/{args.case}/port"}  # fmt: skip
    ok = True
    made = [e for e in envs if e["name"] in runs]  # --first-difference: the runs after the first difference
    faults_made = [f for f in faults if f"fault:{f['name']}" in runs]  # are not made
    entries_made = [e for e in entries if f"entry:{e}" in runs]
    if len(made) < len(envs) or len(faults_made) < len(faults) or len(entries_made) < len(entries):
        report["stopped"] = (
            f"at the first difference: {len(made) + len(faults_made) + len(entries_made)} of "
            f"{len(envs) + len(faults) + len(entries)} runs"
        )
    for i, env in enumerate(made):
        run = compare_run(case, corpus, cobol, runs[env["name"]])
        if i == 0:  # the first environment's outputs are the report's, as before #3821
            report["return_code"], report["outputs"], report["abend"] = run["return_code"], run["outputs"], run["abend"]
            report["sysout"] = run.get("sysout")
        report.setdefault("environments", []).append({**env, "ok": run["ok"], "return_code": run["return_code"],
                                                      "outputs": run["outputs"], "abend": run["abend"]})  # fmt: skip
        ok &= run["ok"]
    for f in faults_made:  # #4023 follow-up: each fault run, proven like the normal one
        run = compare_run(case, corpus, cobol_faults[f["name"]], runs[f"fault:{f['name']}"], fault=f)
        report.setdefault("faults", []).append({"name": f["name"], "why": f.get("why", ""), "plan": fault_plan(f)
                                                .strip().splitlines(), **run})  # fmt: skip
        ok &= run["ok"]
    whys = {e["method"]: e.get("why", "") for e in case.get("entries", [])}
    for e in entries_made:  # #4048 follow-up: each entry run, against the same COBOL run as the normal one
        run = compare_run(case, corpus, cobol, runs[f"entry:{e}"])
        report.setdefault("entries", []).append({"method": e, "why": whys[e], **run})
        ok &= run["ok"]
    rc = report["return_code"]
    report["proven"] = ok
    traces = [work / "cobol" / cov.TRACE_NAME] + [
        work / "faults" / f["name"] / "cobol" / cov.TRACE_NAME for f in faults
    ]
    report["coverage"] = cobol_coverage(case, corpus, traces, work / "coverage.json")  # #4023, every run together
    report["runs"] = 1 + len(faults)
    report["oracle"] = equivalence_oracle.for_case(case)  # #4309: which GnuCOBOL produced the expected outputs
    report["feedback"] = feedback_md(report) if not ok else ""
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (work / "report.md").write_text(report_markdown(case, report), encoding="utf-8")
    if report["abend"]["cobol"] or report["abend"]["java"]:
        print(f"{case['program']} ABEND: COBOL {report['abend']['cobol']}, Java {report['abend']['java']}")
    print(
        f"{case['program']} RETURN-CODE: COBOL {rc['cobol']}, Java {rc['java']}"
        + ("" if rc["cobol"] == rc["java"] else "  <-- differs")
    )
    for dd, d in report["outputs"].items():
        print(f"{case['program']} {dd}: {d['equal']}/{d['records']} records equal")
        for x in d["diffs"][:10]:
            print(f"   record {x['record']}: {(x.get('missing') and 'missing on ' + x['missing']) or x['fields'][:4]}")
    s = report.get("sysout")
    if s:
        print(f"{case['program']} SYSOUT: " + (f"{s['equal']}/{s['lines']} lines equal" if s["compared"]
                                               else f"not compared -- {s['why']}"))  # fmt: skip
        for x in s.get("diffs", [])[:5]:
            print(f"   line {x['line']}: COBOL {x['cobol']!r}, Java {x['java']!r}")
    if len(envs) > 1:
        for e in report["environments"]:
            print(f"{case['program']} under {e['name']} ({e['locale']}, {e['tz']}): "
                  f"{'equal to COBOL' if e['ok'] else 'DIFFERS'}")  # fmt: skip
    for f in report.get("faults", []):
        print(f"{case['program']} fault {f['name']}: {'equal' if f['ok'] else 'DIFFERS'} -- {f['summary']}")
    for e in report.get("entries", []):
        print(f"{case['program']} entry {e['method']}(): {'equal' if e['ok'] else 'DIFFERS'} -- {e['summary']}")
    if report["coverage"]:
        print(f"{case['program']} COBOL coverage: {cov.headline(report['coverage'], report['runs'], ok)}")
    print(f"report: {work / 'report.json'}")
    return _recorded(args, work, 0 if ok else 1)


def _recorded(args: argparse.Namespace, work: Path, rc: int) -> int:
    """#4048 `--record`: the evidence record of the run just made (report.json in `work`), proven or not."""
    if getattr(args, "record", False) and (work / "report.json").is_file():
        import evidence

        rec = evidence.record_equivalence_run(args.case, work)
        st = evidence.status(rec, evidence.equivalence_target(args.case))
        print(f"evidence: {evidence.rel_path(evidence.equivalence_target(args.case).record)} -- {st['status']}"
              + (f" ({'; '.join(st['reasons'])})" if st["reasons"] else ""))  # fmt: skip
    return rc


if __name__ == "__main__":
    sys.exit(main())
