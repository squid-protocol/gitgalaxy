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

An elementary PIC X item is a CobolRef<String>, its record bytes compared. A group item (IBM DBB EPSNBRVL's
EPS-NUMBER-VALIDATION) is the call forge's contract DTO: the case names its layout,

    "using": [{"name": "EPS-NUMBER-VALIDATION", "size": 129,
               "record": {"copybook": "zBuilder/MortgageApplication/copybook/epsnbrpm.cpy", "name": "EPS-NUMBER-VALIDATION"}}]

and the argument is still the item's text before the call. The Java side receives a DTO built from that text field
by field (decoded with the layout, mapped to the DTO's properties by their offset comments) and writes the DTO it
gets back; the COBOL side's bytes are decoded with the same layout and every field compared by value, as a LINKed
program's COMMAREA is (equivalence_cics._same). A DTO property that nests another DTO is Unsupported.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional

import cobol_coverage as cov
import equivalence_common as common
import equivalence_oracle

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


_DTO_FIELD = re.compile(
    r"//\s*([A-Z0-9-]+):\s*PIC[^\n]*?offset\s+(\d+),\s*(\d+)\s+bytes[^\n]*\n\s*private\s+([\w.<>]+)\s+(\w+);"
)


def dto_items(case: dict[str, Any]) -> bool:
    return any(u.get("record") for u in case["using"])


def item_layout(case: dict[str, Any], corpus: Path, u: dict[str, Any]) -> list[dict[str, Any]]:
    """A group USING item's elementary fields, from its copybook (the harness's own reader, never the translator's)."""
    rec = u["record"]
    dirs = [corpus / d for d in case.get("copy_dirs", [])]
    fields = common.layout_fields(corpus, rec["copybook"], rec.get("name"), copy_dirs=[*dirs, corpus])
    end = max((f["offset"] + f["bytes"] for f in fields), default=0)
    if end != u["size"]:
        raise Unsupported(f"{u['name']}: the case says {u['size']} bytes, its layout {end}")
    return fields


def dto_properties(java_root: Path, cls: str) -> dict[str, tuple[str, str]]:
    """{COBOL field: (DTO property, Java type)} of a contract DTO, from its offset comments."""
    hits = list(java_root.rglob(f"dto/contract/{cls}.java"))
    if len(hits) != 1:
        raise Unsupported(f"no generated contract DTO {cls}")
    text = hits[0].read_text(encoding="utf-8")
    if "->" in text.split("class", 1)[-1]:
        raise Unsupported(f"{cls} nests another DTO: not supported by the call harness")
    return {m.group(1): (m.group(5), m.group(4)) for m in _DTO_FIELD.finditer(text)}


def arg_bytes(case: dict[str, Any], corpus: Path, u: dict[str, Any], arg: Any) -> bytes:
    """A USING item's bytes before the call: its text, or -- a group item's argument given as {field: value}, for
    binary or packed fields text cannot spell -- the record built field by field (unnamed fields INITIALIZEd)."""
    enc = common.data_encoding(case)
    if isinstance(arg, dict):
        import equivalence_cics as ec

        if not u.get("record"):
            raise Unsupported(f"{u['name']}: field values for an item with no record layout")
        return ec.encode_record(item_layout(case, corpus, u), arg, b"init", enc)
    return str(arg).ljust(u["size"]).encode(enc)


def _value(v: Any) -> Any:
    """A decoded field as JSON: an exact decimal as its text, storage a NUMERIC test rejects as null."""
    if isinstance(v, str):
        return None if v.startswith(("<invalid", "<undecodable")) else v.rstrip(" ")
    return str(v)


def reclen(case: dict[str, Any]) -> int:
    return sum(u["size"] for u in case["using"]) + RC_BYTES


def _literal(value: str, size: int) -> str:
    if len(value) > size:
        raise Unsupported(f"argument {value!r} is longer than its item ({size})")
    if len(value) > 50 or "\n" in value:
        raise Unsupported("an argument longer than 50 characters (one source line)")
    return "SPACES" if not value.strip() else "'" + value.replace("'", "''") + "'"


def cobol_driver(case: dict[str, Any], corpus: Optional[Path] = None) -> str:
    """EQCALLDR: each call's items set, the CALL, the items and RETURN-CODE written as one record. An argument given
    as field values is set as its bytes, 16 hexadecimal bytes per MOVE into the item's reference modification."""
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
            if isinstance(v, dict):
                if corpus is None:
                    raise Unsupported("field-value arguments need the corpus")
                b = arg_bytes(case, corpus, u, v)
                lines += [f"    MOVE X'{b[k : k + 16].hex().upper()}' TO {a}({k + 1}:{len(b[k : k + 16])})"
                          for k in range(0, len(b), 16)]  # fmt: skip
                continue
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
    common.stage_copybooks(case, corpus, src)
    common.comp5_layout_guard(src)  # #4751: a 1- or 2-digit COMP-5 is one byte in GnuCOBOL, a halfword on z/OS (C16)
    (src / "EQCALLDR.cbl").write_text(cobol_driver(case, corpus), encoding="ascii")
    stubs = [p for p in [*LE.glob("*.c"), FAULTS / "ggabend.c"] if p.is_file()]
    for p in stubs:
        shutil.copy(p, src / p.name)
    flags = " ".join(["-std=ibm -fsign=EBCDIC", *option_flags, cov.TRACE_FLAG, "-I /work/src"])
    script = ["set -e", "cd /work",
              f"cobc -x {flags} -o call src/EQCALLDR.cbl src/PROGRAM.cbl {' '.join('src/' + p.name for p in stubs)}",
              f"{cov.trace_env('/work/' + cov.TRACE_NAME)}GG_ABEND=/work/ABEND OUTFILE=/work/CALLS.out ./call "
              "> /work/stdout.txt 2>&1"]  # fmt: skip
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    proc = common.run_cobol_step(work)
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

    if dto_items(case):
        return run_java_dto(case, corpus, work, port, port_dir)
    project = ej.prepare_project(case, corpus, work, java_test(case), port, port_dir)
    svc = next((project / "src/main/java").rglob(f"{ej._service_class(case['program'])}.java"), None)
    if svc is None or "handleCall(CobolRef<String>" not in svc.read_text(encoding="utf-8"):
        raise Unsupported(f"{case['program']}'s service has no handleCall(CobolRef<String>, ...) to drive")
    inputs = work / "in"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / "calls.json").write_text(json.dumps([c["args"] for c in case["calls"]]), encoding="utf-8")
    out = ej.run_maven(project, work, inputs, props=ej.data_charset_arg(case))
    return (out / "CALLS.out").read_bytes() if (out / "CALLS.out").is_file() else b""


def handle_call_types(svc_text: str) -> list[str]:
    m = re.search(r"public int handleCall\(([^)]*)\)", svc_text)
    return [p.strip().rsplit(" ", 1)[0] for p in m.group(1).split(",") if p.strip()] if m else []


def dto_args(case: dict[str, Any], corpus: Path, java_root: Path, types: list[str]) -> list[list[Any]]:
    """Each call's arguments as the Java side receives them: a text item's text; a group item's DTO, as JSON."""
    enc = common.data_encoding(case)
    calls = []
    for call in case["calls"]:
        row: list[Any] = []
        for u, arg, typ in zip(case["using"], call["args"], types):
            if not u.get("record"):
                row.append(arg)
                continue
            raw = arg_bytes(case, corpus, u, arg)
            props = dto_properties(java_root, typ)
            obj = {}
            for f in item_layout(case, corpus, u):
                if f["name"] in props:
                    v = common.decode_field(raw[f["offset"] : f["offset"] + f["bytes"]], f["pic"], f["usage"],
                                            common.sign_page(enc), f.get("sign_separate", False), enc)  # fmt: skip
                    obj[props[f["name"]][0]] = _value(v)
            row.append(obj)
        calls.append(row)
    return calls


def run_java_dto(case: dict[str, Any], corpus: Path, work: Path, port: bool, port_dir: Optional[Path]) -> bytes:
    """A case with a group USING item: the Java side's CALLS.json (each call's items and RETURN-CODE)."""
    import equivalence_java as ej

    # the service's signature names the DTO types, so the project is generated first, then the test written to it
    project = ej.prepare_project(case, corpus, work, java_test_dto(case, []), port, port_dir)
    java_root = project / "src/main/java"
    svc = next(java_root.rglob(f"{ej._service_class(case['program'])}.java"), None)
    types = handle_call_types(svc.read_text(encoding="utf-8")) if svc else []
    if len(types) != len(case["using"]):
        raise Unsupported(f"{case['program']}'s service has no handleCall taking its {len(case['using'])} items")
    for u, t in zip(case["using"], types):
        if bool(u.get("record")) == (t == "CobolRef<String>"):
            raise Unsupported(f"{u['name']}: the case and handleCall's {t} disagree on a text vs a group item")
    test = next(project.rglob("EquivalenceRunTest.java"))
    test.write_text(java_test_dto(case, types), encoding="utf-8")
    inputs = work / "in"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / "calls.json").write_text(json.dumps(dto_args(case, corpus, java_root, types)), encoding="utf-8")
    (work / "java_root.txt").write_text(str(java_root), encoding="utf-8")
    (work / "handle_call_types.json").write_text(json.dumps(types), encoding="utf-8")
    out = ej.run_maven(project, work, inputs, props=ej.data_charset_arg(case))
    return (out / "CALLS.json").read_bytes() if (out / "CALLS.json").is_file() else b""


def java_test_dto(case: dict[str, Any], types: list[str]) -> str:
    """The generated JUnit run for group items: each call's items built (a DTO from its JSON), handleCall, and the
    items as the call left them written as JSON with the RETURN-CODE."""
    import equivalence_java as ej

    svc = ej._service_class(case["program"])
    var = svc[0].lower() + svc[1:]
    sets, refs, outs = [], [], []
    for i, t in enumerate(types):
        if t == "CobolRef<String>":
            sets.append(f"            CobolRef<String> a{i} = CobolRef.of(c.get({i}).asText());")
            outs.append(f"            items.add(a{i}.get());")
        else:
            sets.append(f"            {t} a{i} = mapper.treeToValue(c.get({i}), {t}.class);")
            outs.append(f"            items.add(mapper.valueToTree(a{i}));")
        refs.append(f"a{i}")
    body = (
        "\n".join(sets)
        + f"\n            int rc = {var}.handleCall({', '.join(refs)});\n"
        + "            java.util.List<Object> items = new java.util.ArrayList<>();\n"
        + "\n".join(outs)
        if types
        else ""
    )
    cobolref = f"import {ej.PKG}.call.CobolRef;\n" if "CobolRef<String>" in types else ""
    return (
        f"""package {ej.PKG};

{cobolref}import {ej.PKG}.dto.contract.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** The CALLs of {case["program"]} ({case["name"]}), group USING items as DTOs -- generated by tests/tools/equivalence_call.py. */
@SpringBootTest(properties = {{"spring.jpa.show-sql=false", "gitgalaxy.clock={ej._clock(case)}"}})
class EquivalenceRunTest {{

    final Path in = Path.of(System.getProperty("equivalence.in"));
    final Path out = Path.of(System.getProperty("equivalence.out"));
    final ObjectMapper mapper = new ObjectMapper();

    @Autowired {ej.PKG}.service.{svc} {var};

    @Test
    void run() throws IOException {{
        java.util.List<Map<String, Object>> records = new java.util.ArrayList<>();
        for (JsonNode c : mapper.readTree(in.resolve("calls.json").toFile())) {{
{body}
            Map<String, Object> rec = new LinkedHashMap<>();
            rec.put("items", items);
            rec.put("rc", rc);
            records.add(rec);
        }}
        mapper.writeValue(out.resolve("CALLS.json").toFile(), records);
    }}
}}
"""
        if types
        else f"""package {ej.PKG};

/** placeholder: replaced once the service's handleCall types are known (equivalence_call.run_java_dto). */
class EquivalenceRunTest {{
}}
"""
    )


def compare_dto(case: dict[str, Any], corpus: Path, cobol: bytes, java_json: bytes, java_root: Path,
                types: list[str]) -> dict[str, Any]:  # fmt: skip
    """Per call, per item: a text item's text, a group item's every DTO-mapped field by value, then RETURN-CODE."""
    from decimal import Decimal

    import equivalence_cics as ec

    enc = common.data_encoding(case)
    n = reclen(case)
    try:
        java = json.loads(java_json.decode("utf-8"), parse_float=Decimal) if java_json else []
    except ValueError:
        java = []
    diffs, equal = [], 0
    for i in range(len(case["calls"])):
        rec = cobol[i * n : (i + 1) * n]
        if i >= len(java):
            diffs.append({"record": i + 1, "missing": "java"})
            continue
        jrec, fields, off = java[i], [], 0
        for k, u in enumerate(case["using"]):
            item = rec[off : off + u["size"]]
            jv = jrec["items"][k] if k < len(jrec.get("items", [])) else None
            if not u.get("record"):
                cv = item.decode(enc, errors="strict") if item else ""
                if not ec._same(cv, jv):
                    fields.append({"field": u["name"], "cobol": cv.rstrip(), "java": str(jv or "").rstrip()})
            else:
                props = dto_properties(java_root, types[k])
                for f in item_layout(case, corpus, u):
                    if f["name"] not in props:
                        continue
                    cv = _value(common.decode_field(item[f["offset"] : f["offset"] + f["bytes"]], f["pic"], f["usage"],
                                                    common.sign_page(enc), f.get("sign_separate", False), enc))  # fmt: skip
                    jval = (jv or {}).get(props[f["name"]][0])
                    if (cv is None and jval is not None) or not ec._same(cv, jval):
                        fields.append({"field": f"{u['name']}.{f['name']}", "cobol": cv, "java": jval})
            off += u["size"]
        crc = int(rec[off : off + RC_BYTES].decode("ascii")) if rec[off : off + RC_BYTES].strip() else 0
        if crc != jrec.get("rc"):
            fields.append({"field": "RETURN-CODE", "cobol": crc, "java": jrec.get("rc")})
        if fields:
            diffs.append({"record": i + 1, "fields": fields})
        else:
            equal += 1
    return {"records": len(case["calls"]), "equal": equal, "diffs": diffs}


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
    if dto_items(case):
        jw = work / "java"
        diff = compare_dto(case, corpus, cobol, java, Path((jw / "java_root.txt").read_text(encoding="utf-8")),
                           json.loads((jw / "handle_call_types.json").read_text(encoding="utf-8")))  # fmt: skip
    else:
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
              "oracle": equivalence_oracle.for_case(case),  # #4309
              "feedback": "" if ok else feedback_md(case, diff)}  # fmt: skip
    (work / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"{case['program']} CALLS: {diff['equal']}/{diff['records']} calls equal")
    for x in diff["diffs"][:10]:
        print(f"   call {x['record']}: {x.get('fields', [])[:3] or x.get('missing')}")
    if coverage:
        print(f"{case['program']} COBOL coverage: {cov.headline(coverage, len(case['calls']), ok, 'call')}")
    print(f"report: {work / 'report.json'}")
    return 0 if ok else 1
