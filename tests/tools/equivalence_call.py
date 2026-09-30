"""
The equivalence harness for a CALLed subprogram (#4023 follow-up): a case with `"kind": "call"`.

A subprogram has no datasets of its own to compare: what it does is what it leaves in its caller's storage -- its
BY REFERENCE USING items -- and its RETURN-CODE. So a case lists CALLs, each with the value of every USING item
before the call:

    "kind": "call", "program": "CSUTLDTC", "program_source": "app/cbl/CSUTLDTC.cbl",
    "using": [{"name": "LS-DATE", "size": 10}, {"name": "LS-DATE-FORMAT", "size": 10}, {"name": "LS-RESULT", "size": 80}],
    "calls": [{"name": "iso-date", "args": ["2022-07-18", "YYYY-MM-DD", ""], "why": "..."}]

COBOL side -- a generated driver (EQCALLDR) sets the items, CALLs the program, and writes one record per call:
every item as the call left it, then RETURN-CODE (S9(4) SIGN LEADING SEPARATE). Built with GnuCOBOL like the
other cases (-ftraceall: coverage), with the harness's LE service models (tests/equivalence/le: CEEDAYS) and the
abend stub. Java side -- the generated service's handleCall(CobolRef<String>, ...) (the call forge's signature:
each BY REFERENCE item a CobolRef, the RETURN-CODE returned), driven by a generated JUnit test that writes the same
record. The records are compared field by field, as a batch output is.

Only elementary PIC X items are supported (each a CobolRef<String>); a numeric or group item is Unsupported.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

import cobol_coverage as cov
import equivalence_common as common

from gitgalaxy.core.source_text import decode_bytes

LE = common.CASES / "le"
FAULTS = common.CASES / "faults"
RC_BYTES = 5  # RETURN-CODE as S9(4) SIGN LEADING SEPARATE


class Unsupported(Exception):
    pass


def record_fields(case: dict[str, Any]) -> list[dict[str, Any]]:
    """The layout of one call's record: every USING item, then RETURN-CODE."""
    fields, off = [], 0
    for u in case["using"]:
        fields.append({"name": u["name"], "offset": off, "bytes": u["size"], "pic": f"X({u['size']})",
                       "usage": "DISPLAY"})  # fmt: skip
        off += u["size"]
    fields.append({"name": "RETURN-CODE", "offset": off, "bytes": RC_BYTES, "pic": "S9(4)", "usage": "DISPLAY",
                   "sign_separate": True})  # fmt: skip
    return fields


def reclen(case: dict[str, Any]) -> int:
    return sum(u["size"] for u in case["using"]) + RC_BYTES


def _literal(value: str, size: int) -> str:
    if len(value) > size:
        raise Unsupported(f"argument {value!r} is longer than its item ({size})")
    if len(value) > 50 or "\n" in value:
        raise Unsupported("an argument longer than 50 characters (one source line)")
    return "SPACES" if not value.strip() else "'" + value.replace("'", "''") + "'"


def cobol_driver(case: dict[str, Any]) -> str:
    """EQCALLDR: each call's items set, the CALL, the items and RETURN-CODE written as one record."""
    items = [f"A{i}" for i in range(len(case["using"]))]
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. EQCALLDR.", "ENVIRONMENT DIVISION.", "INPUT-OUTPUT SECTION.",
             "FILE-CONTROL.", "    SELECT OUT-F ASSIGN TO OUTFILE ORGANIZATION IS SEQUENTIAL.", "DATA DIVISION.",
             "FILE SECTION.", "FD  OUT-F.", f"01  OUT-R PIC X({reclen(case)}).", "WORKING-STORAGE SECTION.",
             "01  CALL-REC."]  # fmt: skip
    lines += [f"    05 {a} PIC X({u['size']})." for a, u in zip(items, case["using"])]
    lines += ["    05 RC-OUT PIC S9(4) SIGN LEADING SEPARATE.", "PROCEDURE DIVISION.", "    OPEN OUTPUT OUT-F"]
    for call in case["calls"]:
        args = call["args"]
        if len(args) != len(items):
            raise Unsupported(f"call {call['name']}: {len(args)} arguments for {len(items)} USING items")
        for a, u, v in zip(items, case["using"], args):
            lines.append(f"    MOVE {_literal(v, u['size'])} TO {a}")
        lines += ["    MOVE 0 TO RETURN-CODE", f"    CALL '{case['program']}' USING {' '.join(items)}",
                  "    MOVE RETURN-CODE TO RC-OUT", "    WRITE OUT-R FROM CALL-REC"]  # fmt: skip
    lines += ["    CLOSE OUT-F", "    MOVE 0 TO RETURN-CODE", "    STOP RUN."]
    return "".join(f"       {x}\n" for x in lines)


def run_cobol(case: dict[str, Any], corpus: Path, work: Path) -> bytes:
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    source, staged = common.read_program(case, corpus / case["program_source"])
    program, option_flags = common.compile_options(case, source)
    (src / "PROGRAM.cbl").write_text(program, encoding=staged)
    for cpy in case.get("copy_dirs", []):
        for p in (corpus / cpy).iterdir():
            if p.is_file():
                shutil.copy(p, src / p.name)
    (src / "EQCALLDR.cbl").write_text(cobol_driver(case), encoding="ascii")
    stubs = [p for p in [*LE.glob("*.c"), FAULTS / "ggabend.c"] if p.is_file()]
    for p in stubs:
        shutil.copy(p, src / p.name)
    flags = " ".join(["-std=ibm -fsign=EBCDIC", *option_flags, cov.TRACE_FLAG, "-I /work/src"])
    script = ["set -e", "cd /work",
              f"cobc -x {flags} -o call src/EQCALLDR.cbl src/PROGRAM.cbl {' '.join('src/' + p.name for p in stubs)}",
              f"{cov.trace_env('/work/' + cov.TRACE_NAME)}GG_ABEND=/work/ABEND OUTFILE=/work/CALLS.out ./call "
              "> /work/stdout.txt 2>&1"]  # fmt: skip
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    proc = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/work", common.IMAGE, "bash", "/work/run.sh"],  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        out = decode_bytes((work / "stdout.txt").read_bytes()) if (work / "stdout.txt").is_file() else ""
        raise RuntimeError(f"COBOL side failed:\n{proc.stdout}\n{proc.stderr}\n{out}")
    return (work / "CALLS.out").read_bytes()


def java_test(case: dict[str, Any]) -> str:
    """The generated JUnit run: each call through the service's handleCall, its record written as the COBOL's."""
    import equivalence_java as ej

    svc = ej._service_class(case["program"])
    var = svc[0].lower() + svc[1:]
    refs = ", ".join(f"a{i}" for i in range(len(case["using"])))
    sets = "\n".join(f"            CobolRef<String> a{i} = CobolRef.of(pad(c.get({i}).asText(), {u['size']}));"
                     for i, u in enumerate(case["using"]))  # fmt: skip
    rec = " + ".join(f"pad(a{i}.get(), {u['size']})" for i, u in enumerate(case["using"]))
    return f"""package {ej.PKG};

import {ej.PKG}.call.CobolRef;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** #4023 follow-up: the CALLs of {case["program"]} ({case["name"]}) -- generated by tests/tools/equivalence_call.py. */
@SpringBootTest(properties = {{"spring.jpa.show-sql=false", "gitgalaxy.clock={ej._clock(case)}"}})
class EquivalenceRunTest {{

    static final Charset TEXT = {common.java_charset(common.data_encoding(case))};
    final Path in = Path.of(System.getProperty("equivalence.in"));
    final Path out = Path.of(System.getProperty("equivalence.out"));

    @Autowired {ej.PKG}.service.{svc} {var};

    @Test
    void run() throws IOException {{
        try (OutputStream o = Files.newOutputStream(out.resolve("CALLS.out"))) {{
            for (JsonNode c : new ObjectMapper().readTree(in.resolve("calls.json").toFile())) {{
{sets}
                int rc = {var}.handleCall({refs});
                o.write(({rec} + String.format(Locale.ROOT, "%s%04d", rc < 0 ? "-" : "+", Math.abs(rc) % 10000))
                        .getBytes(TEXT));
            }}
        }}
    }}

    static String pad(Object v, int n) {{
        String s = v == null ? "" : v.toString();
        return s.length() >= n ? s.substring(0, n) : s + " ".repeat(n - s.length());
    }}
}}
"""


def run_java(case: dict[str, Any], corpus: Path, work: Path, port: bool, port_dir: Optional[Path]) -> bytes:
    import equivalence_java as ej

    project = ej.prepare_project(case, corpus, work, java_test(case), port, port_dir)
    svc = next((project / "src/main/java").rglob(f"{ej._service_class(case['program'])}.java"), None)
    if svc is None or "handleCall(CobolRef<String>" not in svc.read_text(encoding="utf-8"):
        raise Unsupported(f"{case['program']}'s service has no handleCall(CobolRef<String>, ...) to drive")
    inputs = work / "in"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / "calls.json").write_text(json.dumps([c["args"] for c in case["calls"]]), encoding="utf-8")
    out = ej.run_maven(project, work, inputs)
    return (out / "CALLS.out").read_bytes() if (out / "CALLS.out").is_file() else b""


def feedback_md(case: dict[str, Any], diff: dict[str, Any]) -> str:
    """Per call that differs: the call, its arguments, and every item that came back different."""
    out = []
    for x in diff["diffs"][:12]:
        call = case["calls"][x["record"] - 1] if x["record"] <= len(case["calls"]) else {"name": "?", "args": []}
        out += [f"### CALL {call['name']} with {json.dumps(call['args'])}", ""]
        if x.get("missing"):
            out.append(f"- no record on the {'COBOL' if x['missing'] == 'cobol' else 'Java'} side")
        for fd in x.get("fields", []):
            out.append(f"- {fd['field']}: COBOL `{fd['cobol']}`, Java `{fd['java']}`")
        out.append("")
    return "\n".join(out).strip()


def run_case(case: dict[str, Any], corpus: Path, work: Path, port: bool = True, port_dir: Optional[Path] = None,
             cobol_only: bool = False) -> int:  # fmt: skip
    cobol = run_cobol(case, corpus, work / "cobol")
    n = reclen(case)
    if cobol_only:
        for i, call in enumerate(case["calls"]):
            print(f"{call['name']}: {cobol[i * n : (i + 1) * n].decode('latin-1')!r}")
        return 0
    try:
        java = run_java(case, corpus, work / "java", port, port_dir)
    except RuntimeError as e:
        failed = common.java_failure_report(case, work, str(e))
        (work / "report.json").write_text(json.dumps(failed, indent=2) + "\n", encoding="utf-8")
        print(f"{case['program']}: the Java side failed -- see {work / 'report.json'}")
        return 1
    diff = common.diff_records(cobol, java, n, record_fields(case), case.get("code_page", "cp037"),
                           common.data_encoding(case))  # fmt: skip
    ok = diff["equal"] == diff["records"] == len(case["calls"]) and not diff["diffs"]
    source, staged = common.read_program(case, corpus / case["program_source"])
    program, _flags = common.compile_options(case, source)
    coverage = cov.write_run_coverage(work / "coverage.json", source=corpus / case["program_source"], original=source,
                                      compiled=program, traces=[work / "cobol" / cov.TRACE_NAME],
                                      compiled_name="PROGRAM.cbl", copybooks=corpus, encoding=staged)  # fmt: skip
    report = {"case": case["name"], "program": case["program"], "kind": "call", "proven": ok,
              "outputs": {"CALLS": diff}, "coverage": coverage,
              "feedback": "" if ok else feedback_md(case, diff)}  # fmt: skip
    (work / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"{case['program']} CALLS: {diff['equal']}/{diff['records']} calls equal")
    for x in diff["diffs"][:10]:
        print(f"   call {x['record']}: {x.get('fields', [])[:3] or x.get('missing')}")
    if coverage:
        print(f"{case['program']} COBOL coverage: {cov.headline(coverage, len(case['calls']), ok, 'call')}")
    print(f"report: {work / 'report.json'}")
    return 0 if ok else 1
