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
NUMPROC(PFD), TRUNC(OPT) -- stops the run (equivalence_common.compile_options). A case's
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

A case with `"kind": "cics"` is an online program (#3754, equivalence_cics.py): its
EXEC CICS is translated to calls into a stub runtime, each scenario (COMMAREA, key
pressed, screen input) runs as one task on both sides -- the Java as a CicsTask through
the service's runTask -- and the tasks' events (SEND MAP, SEND TEXT, RETURN, XCTL, ABEND)
are compared field by field.
"""

from __future__ import annotations

import argparse
import codecs
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cobol_coverage as cov  # noqa: E402 -- #4023

# The primitives every harness module shares live in a leaf module (no cycle); re-exported here.
from equivalence_common import (
    CASES,
    DEFAULT_DATA_ENCODING,
    IMAGE,
    _fixed,
    _input_path,
    compile_options,
    data_encoding,
    decode_field,
    layout_fields,
    read_program,
    require_ascii_runtime,
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


def run_cobol(case: dict[str, Any], corpus: Path, work: Path) -> dict[str, bytes]:
    """Stage, compile and run the case's program under GnuCOBOL; {dd: output bytes}."""
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    # #3828: the program's CBL / PROCESS cards and the case's `compiler_options` become cobc flags
    require_ascii_runtime(case)  # #3815: an EBCDIC data page cannot run under GnuCOBOL
    enc = data_encoding(case)
    # #3815: read by the engine's ladder (or the declared page), staged in the encoding it was read in
    source, staged = read_program(case, corpus / case["program_source"])
    program, option_flags = compile_options(case, source)
    (src / "PROGRAM.cbl").write_text(program, encoding=staged)
    for cpy in case.get("copy_dirs", []):
        for p in (corpus / cpy).iterdir():
            if p.is_file():
                shutil.copy(p, src / p.name)
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
    script.append(f"cobc -x {flags} {cov.TRACE_FLAG} -o program src/EQDRIVER.cbl src/PROGRAM.cbl")  # #4023: traced
    env = " ".join(f"{dd}=/work/{dd}.idx" for dd in case["datasets"])
    clock = f"COB_CURRENT_DATE='{case['clock']}' " if case.get("clock") else ""
    tz = f"TZ='{case['zone']}' " if case.get("zone") else ""
    # the step's RETURN-CODE is an output like any other (CBTRN02C sets 4 when it rejects): recorded, not fatal
    script.append(f"set +e; {cov.trace_env('/work/' + cov.TRACE_NAME)}{tz}{clock}{env} ./program > /work/stdout.txt 2>&1; "
                  "echo $? > /work/RETURN-CODE; set -e")  # fmt: skip
    for dd, spec in case["datasets"].items():
        if spec.get("compare") and spec.get("organization") == "indexed":
            script.append(f"{dd}=/work/{dd}.idx OUTFILE=/work/{dd}.out ./ul{dd}")
        elif spec.get("compare"):
            script.append(f"cp /work/{dd}.idx /work/{dd}.out")
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    proc = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{work}:/work", IMAGE, "bash", "/work/run.sh"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"COBOL side failed:\n{proc.stdout}\n{proc.stderr}")
    # #4023: how much of the program this run executes (work/coverage.json)
    cov.write_run_coverage(work / "coverage.json", source=corpus / case["program_source"], original=source,
                           compiled=program, traces=[work / cov.TRACE_NAME], compiled_name="PROGRAM.cbl",
                           copybooks=corpus, encoding=staged)  # fmt: skip
    outs = {dd: (work / f"{dd}.out").read_bytes() for dd, spec in case["datasets"].items() if spec.get("compare")}
    outs["RETURN-CODE"] = (work / "RETURN-CODE").read_text(encoding="ascii").strip().encode()
    return outs


def build_image() -> None:
    subprocess.run(
        ["docker", "build", "-q", "-t", IMAGE, "-f", str(CASES / "gnucobol.Dockerfile"), str(CASES)],
        check=True, capture_output=True,
    )  # fmt: skip


# ---- the field-by-field diff ---------------------------------------------------------
# #3815: the usages whose bytes are characters in the data's page (the rest -- COMP, COMP-3 -- are binary)
_TEXT_USAGES = frozenset({"DISPLAY"})


def _as_text(raw: bytes, enc: str) -> Any:
    """#3815: bytes as text in `enc`, or the bytes themselves when they are not text there (never lost)."""
    try:
        return raw.decode(enc)
    except UnicodeDecodeError:
        return raw


def diff_records(
    left: bytes,
    right: bytes,
    reclen: int,
    fields: list[dict[str, Any]],
    code_page: str = "cp037",
    data_encoding: str = DEFAULT_DATA_ENCODING,
    right_encoding: Optional[str] = None,
) -> dict[str, Any]:
    """Pair records in order; per pair, every differing field (value left vs right). A field whose value is
    equal but whose bytes are not (a C vs F sign nibble, -0 vs +0) is a difference too, marked `raw` and
    shown as hex (#3830): the files differ, and a later program may test the sign. A FILLER is counted
    apart (`filler_differs`), not as a difference: no program can name it, so what it holds after an
    INITIALIZE or a new record is the runtime's leftover record area, not the program's logic.

    #3820: the bytes no field covers are compared too, as `(bytes outside the layout)`. The layout is
    read from the copybook, so a width it gets wrong (a currency string sized as one byte) leaves the
    record's tail -- where the real later fields sit -- unread: comparing only the listed fields let
    two different records pass as equal. `layout_bytes` reports the layout's own width beside `reclen`.

    #3815: text and zoned fields are decoded in `data_encoding` (the case's page, default Latin-1), the right
    side in `right_encoding` when it was written in another (a mainframe's cp277 unload against a run in
    ISO-8859-1): then the same text in two pages is equal, and only a binary field's (COMP / COMP-3) bytes,
    which no page changes, are compared as bytes; FILLER and the bytes outside the layout are compared as text.
    Across pages, a record's layout must fit both (single-byte pages): offsets are bytes."""
    renc = right_encoding or data_encoding
    same_page = codecs.lookup(renc).name == codecs.lookup(data_encoding).name

    def same_bytes(x: bytes, y: bytes, usage: Optional[str] = None) -> bool:
        if same_page or (usage or "DISPLAY").upper() not in _TEXT_USAGES:
            return x == y
        return _as_text(x, data_encoding) == _as_text(y, renc)

    covered = bytearray(reclen)
    for f in fields:
        for i in range(max(f["offset"], 0), min(f["offset"] + f["bytes"], reclen)):
            covered[i] = 1
    layout_bytes = max((f["offset"] + f["bytes"] for f in fields), default=0)
    lrecs = [left[i : i + reclen] for i in range(0, len(left), reclen)]
    rrecs = [right[i : i + reclen] for i in range(0, len(right), reclen)]
    diffs, equal, filler = [], 0, 0
    for n in range(max(len(lrecs), len(rrecs))):
        a = lrecs[n] if n < len(lrecs) else None
        b = rrecs[n] if n < len(rrecs) else None
        if a is None or b is None:
            diffs.append({"record": n + 1, "missing": "cobol" if a is None else "java"})
            continue
        bad, filler_bad = [], False
        for f in fields:
            sl = slice(f["offset"], f["offset"] + f["bytes"])
            sep = f.get("sign_separate", False)
            va, vb = (
                decode_field(a[sl], f["pic"], f["usage"], code_page, sep, data_encoding),
                decode_field(b[sl], f["pic"], f["usage"], code_page, sep, renc),
            )
            if not same_bytes(a[sl], b[sl], f["usage"]) and f["name"] == "FILLER":
                filler_bad = True
            elif va != vb:
                bad.append({"field": f["name"], "cobol": str(va), "java": str(vb)})
            elif not same_bytes(a[sl], b[sl], f["usage"]):  # #3830: same value, other bytes -- C vs F sign, -0 / +0
                bad.append({"field": f["name"], "cobol": a[sl].hex(), "java": b[sl].hex(), "raw": True})
        outside = [
            i
            for i in range(max(len(a), len(b)))
            if (i >= reclen or not covered[i]) and not same_bytes(a[i : i + 1], b[i : i + 1])
        ]
        if outside:
            lo, hi = outside[0], outside[-1] + 1
            bad.append(
                {"field": f"(bytes outside the layout @{lo}..{hi})", "cobol": repr(a[lo:hi]), "java": repr(b[lo:hi])}
            )
        filler += filler_bad
        if bad:
            diffs.append({"record": n + 1, "fields": bad})
        else:
            equal += 1
    return {"records": max(len(lrecs), len(rrecs)), "equal": equal, "diffs": diffs, "filler_differs": filler,
            "layout_bytes": layout_bytes}  # fmt: skip


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
    lines += cov.report_lines(report.get("coverage"), 1, report.get("proven", False))  # #4023
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


# ---- CLI -----------------------------------------------------------------------------
def load_case(name: str) -> dict[str, Any]:
    case = json.loads((CASES / name / "case.json").read_text(encoding="utf-8"))
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
    r.add_argument("--generated-only", action="store_true",
                   help="run the generated service as generated (no port): the generator's own baseline")  # fmt: skip
    sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "list":
        for p in sorted(CASES.glob("*/case.json")):
            print(p.parent.name)
        return 0
    import mainframe_corpus as mc

    case = load_case(args.case)
    for key in ("source_encoding", "data_encoding"):  # #3815: the CLI overrides the case
        if getattr(args, key):
            case[key] = getattr(args, key)
    data_encoding(case)  # a bad declaration fails here, not after the COBOL build
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    work = args.keep or Path(tempfile.mkdtemp(prefix=f"equiv_{args.case}_"))
    build_image()
    if case.get("kind") == "cics":  # #3754: an online program, run as tasks under the stub CICS runtime
        import equivalence_cics as ec

        return ec.run_case(case, corpus, work, port=not args.generated_only, port_dir=args.port,
                           cobol_only=args.cobol_only)  # fmt: skip
    cobol = run_cobol(case, corpus, work / "cobol")
    if args.cobol_only:
        for dd, data in cobol.items():
            if dd == "RETURN-CODE":
                print(f"RETURN-CODE: {data.decode()}")
                continue
            print(f"{dd}: {len(data)} bytes, {len(data) // case['datasets'][dd]['reclen']} records")
        return 0
    import equivalence_java as ej

    envs = _environments(args.environments, case)
    runs = ej.run_java_environments(case, corpus, work / "java", work / "cobol", envs, port=not args.generated_only,
                                    port_dir=args.port)  # fmt: skip
    report: dict[str, Any] = {"case": args.case, "program": case["program"], "outputs": {},
                              "java": "generated" if args.generated_only else "ported", "collation": COLLATION,
                              "port": str(args.port) if args.port else f"tests/equivalence/{args.case}/port"}  # fmt: skip
    ok = True
    for i, env in enumerate(envs):
        java = runs[env["name"]]
        rc = {"cobol": cobol.get("RETURN-CODE", b"").decode(), "java": java.get("RETURN-CODE", b"").decode()}
        env_ok, outputs = rc["cobol"] == rc["java"], {}
        for dd, spec in case["datasets"].items():
            if not spec.get("compare"):
                continue
            fields = layout_fields(corpus, spec["copybook"], spec.get("record"))
            d = diff_records(cobol[dd], java.get(dd, b""), spec["reclen"], fields, case.get("code_page", "cp037"),
                             data_encoding(case))  # fmt: skip
            if d["layout_bytes"] != spec["reclen"]:  # #3820: the copybook's layout does not fill the record
                print(f"{case['program']} {dd}: layout is {d['layout_bytes']} bytes, reclen {spec['reclen']}")
            outputs[dd] = d
            env_ok &= d["equal"] == d["records"] and not d["diffs"]
        if i == 0:  # the first environment's outputs are the report's, as before #3821
            report["return_code"], report["outputs"] = rc, outputs
        report.setdefault("environments", []).append({**env, "ok": env_ok, "return_code": rc, "outputs": outputs})
        ok &= env_ok
    rc = report["return_code"]
    report["proven"] = ok
    covered = work / "cobol" / "coverage.json"  # #4023
    report["coverage"] = json.loads(covered.read_text(encoding="utf-8")) if covered.is_file() else None
    if report["coverage"] and "error" in report["coverage"]:
        report["coverage"] = None
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (work / "report.md").write_text(report_markdown(case, report), encoding="utf-8")
    print(
        f"{case['program']} RETURN-CODE: COBOL {rc['cobol']}, Java {rc['java']}"
        + ("" if rc["cobol"] == rc["java"] else "  <-- differs")
    )
    for dd, d in report["outputs"].items():
        print(f"{case['program']} {dd}: {d['equal']}/{d['records']} records equal")
        for x in d["diffs"][:10]:
            print(f"   record {x['record']}: {(x.get('missing') and 'missing on ' + x['missing']) or x['fields'][:4]}")
    if len(envs) > 1:
        for e in report["environments"]:
            print(f"{case['program']} under {e['name']} ({e['locale']}, {e['tz']}): "
                  f"{'equal to COBOL' if e['ok'] else 'DIFFERS'}")  # fmt: skip
    if report["coverage"]:
        print(f"{case['program']} COBOL coverage: {cov.headline(report['coverage'], 1, ok)}")
    print(f"report: {work / 'report.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
