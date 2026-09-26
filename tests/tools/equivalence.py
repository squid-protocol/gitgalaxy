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

COBOL side -- GnuCOBOL 3.x (BDB indexed files) in a container built from
tests/equivalence/gnucobol.Dockerfile. Each KSDS input is loaded by a generated
loader keyed like the program's SELECT (alternate keys included); the program runs
under a generated driver that passes the JCL PARM through LINKAGE, with
COB_CURRENT_DATE pinning FUNCTION CURRENT-DATE; each output (and each KSDS the
program opens I-O) is unloaded to fixed-length records. Compiled `-std=ibm
-fsign=EBCDIC`: the corpus data is EBCDIC-style zoned (`{` = +0) in ASCII text.

Java side -- the generated project (the refractor + cobol-to-java pipeline, target
config `h2`) with the case's hand-ported sources overlaid (the vertical slice), run
by a generated JUnit test: inputs are loaded through the entities' record codecs
into H2, the step's `runBatch(dds)` runs, outputs are dumped through the same
codecs and the DatasetResolver's files.

Diff -- per output: records paired in order (a KSDS in key order), every field of the
copybook layout compared -- numeric DISPLAY / COMP-3 / COMP as exact decimals,
everything else byte for byte. The report gives, per program, records equal /
total and every differing field.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = REPO_ROOT / "tests" / "equivalence"
IMAGE = "gitgalaxy-gnucobol:3"
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---- COBOL side ----------------------------------------------------------------------
def _cbl(lines: list[str]) -> str:
    """Fixed-format COBOL: each line in columns 8-72 (area A at 8)."""
    out = []
    for ln in lines:
        body = ln.rstrip()
        assert len(body) <= 65, f"COBOL line too long: {body!r}"  # noqa: S101 -- generated text, a harness bug
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


def _fixed(src: Path, reclen: int) -> bytes:
    """A corpus data file (text lines) as fixed-length records: CR dropped, each line padded."""
    out = bytearray()
    for line in src.read_bytes().split(b"\n"):
        line = line.rstrip(b"\r")
        if line:
            out += line[:reclen].ljust(reclen, b" ")
    return bytes(out)


def _input_path(case: dict[str, Any], corpus: Path, rel: str) -> Path:
    """A dataset's input: `@case/...` is a file of the case directory, else the corpus's."""
    return CASES / case["name"] / rel[len("@case/") :] if rel.startswith("@case/") else corpus / rel


def run_cobol(case: dict[str, Any], corpus: Path, work: Path) -> dict[str, bytes]:
    """Stage, compile and run the case's program under GnuCOBOL; {dd: output bytes}."""
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    shutil.copy(corpus / case["program_source"], src / "PROGRAM.cbl")
    for cpy in case.get("copy_dirs", []):
        for p in (corpus / cpy).iterdir():
            if p.is_file():
                shutil.copy(p, src / p.name)
    script = ["set -e", "cd /work"]
    flags = "-std=ibm -fsign=EBCDIC -I /work/src"
    for dd, spec in case["datasets"].items():
        if "input" in spec:
            (work / f"{dd}.in").write_bytes(_fixed(_input_path(case, corpus, spec["input"]), spec["reclen"]))
        if spec.get("organization") == "indexed":
            (src / f"LD{dd}.cbl").write_text(cobol_loader(dd, spec["reclen"], spec["keys"]), encoding="ascii")
            (src / f"UL{dd}.cbl").write_text(cobol_unloader(dd, spec["reclen"], spec["keys"]), encoding="ascii")
            script += [f"cobc -x {flags} -o ld{dd} src/LD{dd}.cbl", f"cobc -x {flags} -o ul{dd} src/UL{dd}.cbl"]
            if "input" in spec:
                script.append(f"INFILE=/work/{dd}.in {dd}=/work/{dd}.idx ./ld{dd}")
        elif "input" in spec:
            script.append(f"cp /work/{dd}.in /work/{dd}.idx")
    (src / "EQDRIVER.cbl").write_text(cobol_driver(case["program"], case.get("parm")), encoding="ascii")
    script.append(f"cobc -x {flags} -o program src/EQDRIVER.cbl src/PROGRAM.cbl")
    env = " ".join(f"{dd}=/work/{dd}.idx" for dd in case["datasets"])
    clock = f"COB_CURRENT_DATE='{case['clock']}' " if case.get("clock") else ""
    script.append(f"{clock}{env} ./program > /work/stdout.txt 2>&1 || (cat /work/stdout.txt; exit 1)")
    for dd, spec in case["datasets"].items():
        if spec.get("compare") and spec.get("organization") == "indexed":
            script.append(f"{dd}=/work/{dd}.idx OUTFILE=/work/{dd}.out ./ul{dd}")
        elif spec.get("compare"):
            script.append(f"cp /work/{dd}.idx /work/{dd}.out")
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    proc = subprocess.run(  # noqa: S603 -- fixed argv, a local image
        ["docker", "run", "--rm", "-v", f"{work}:/work", IMAGE, "bash", "/work/run.sh"],  # noqa: S607
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"COBOL side failed:\n{proc.stdout}\n{proc.stderr}")
    return {dd: (work / f"{dd}.out").read_bytes() for dd, spec in case["datasets"].items() if spec.get("compare")}


def build_image() -> None:
    subprocess.run(  # noqa: S603
        ["docker", "build", "-q", "-t", IMAGE, "-f", str(CASES / "gnucobol.Dockerfile"), str(CASES)],  # noqa: S607
        check=True, capture_output=True,
    )  # fmt: skip


# ---- the field-by-field diff ---------------------------------------------------------
_OVERPUNCH = {**{c: (i, 1) for i, c in enumerate("{ABCDEFGHI")}, **{c: (i, -1) for i, c in enumerate("}JKLMNOPQR")}}


def _pic_numeric(pic: str) -> Optional[tuple[bool, int, int]]:
    """(signed, digits, scale) of a numeric PIC, or None."""
    import re

    p = re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())
    if not p or re.search(r"[^S9V]", p):
        return None
    whole, _, frac = p.partition("V")
    return p.startswith("S"), whole.count("9") + frac.count("9"), frac.count("9")


def decode_field(raw: bytes, pic: Optional[str], usage: Optional[str]) -> Any:
    """A field's value: an exact Decimal for numeric DISPLAY / COMP-3 / COMP, else its text."""
    num = _pic_numeric(pic) if pic else None
    u = (usage or "DISPLAY").upper()
    if num is None:
        return raw.decode("latin-1")
    signed, _digits, scale = num
    try:
        if u in ("COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"):
            hexs = raw.hex()
            value, sign = int(hexs[:-1]), hexs[-1]
            return Decimal(-value if sign in "bd" else value).scaleb(-scale)
        if u in ("COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"):
            return Decimal(int.from_bytes(raw, "big", signed=signed)).scaleb(-scale)
        text = raw.decode("latin-1")
        last, sign = text[-1], 1
        if last in _OVERPUNCH:
            d, sign = _OVERPUNCH[last]
            text = text[:-1] + str(d)
        return (Decimal(int(text)) * sign).scaleb(-scale)
    except (ValueError, IndexError):
        return f"<invalid {raw!r}>"


def layout_fields(corpus: Path, copybook: str, record: Optional[str] = None) -> list[dict[str, Any]]:
    """The elementary fields of a copybook record: name, offset, bytes, pic, usage (the answer
    key's own reader and storage arithmetic, cobol_answer_key)."""
    import cobol_answer_key as ak

    items = [it for it in ak._data_items(ak.Source(corpus / copybook)) if it["level"] not in (66, 88)]
    kids: dict[Optional[int], list[dict[str, Any]]] = {}
    for it in items:
        kids.setdefault(it["parent"], []).append(it)

    def size(it: dict[str, Any]) -> int:
        if it.get("pic"):
            own = ak._pic_bytes(it["pic"], it.get("usage"), it.get("sign_separate", False))
        else:
            own = sum(size(c) for c in kids.get(it["ordinal"], []) if not c.get("redefines"))
        return own * (it.get("occurs_max") or 1)

    out: list[dict[str, Any]] = []

    def place(it: dict[str, Any], at: int) -> None:
        if it.get("pic"):
            out.append(
                {"name": it["name"], "offset": at, "bytes": size(it), "pic": it["pic"], "usage": it.get("usage")}
            )
            return
        cur = at
        for c in kids.get(it["ordinal"], []):
            if c.get("redefines"):
                continue
            place(c, cur)
            cur += size(c)

    roots = [r for r in kids.get(None, []) if not r.get("redefines") and (record is None or r["name"] == record)]
    place(roots[0], 0)
    return out


def diff_records(left: bytes, right: bytes, reclen: int, fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Pair records in order; per pair, every differing field (value left vs right)."""
    lrecs = [left[i : i + reclen] for i in range(0, len(left), reclen)]
    rrecs = [right[i : i + reclen] for i in range(0, len(right), reclen)]
    diffs, equal = [], 0
    for n in range(max(len(lrecs), len(rrecs))):
        a = lrecs[n] if n < len(lrecs) else None
        b = rrecs[n] if n < len(rrecs) else None
        if a is None or b is None:
            diffs.append({"record": n + 1, "missing": "cobol" if a is None else "java"})
            continue
        bad = []
        for f in fields:
            sl = slice(f["offset"], f["offset"] + f["bytes"])
            va, vb = decode_field(a[sl], f["pic"], f["usage"]), decode_field(b[sl], f["pic"], f["usage"])
            if va != vb:
                bad.append({"field": f["name"], "cobol": str(va), "java": str(vb)})
        if bad:
            diffs.append({"record": n + 1, "fields": bad})
        else:
            equal += 1
    return {"records": max(len(lrecs), len(rrecs)), "equal": equal, "diffs": diffs}


def report_markdown(case: dict[str, Any], report: dict[str, Any]) -> str:
    """The run as Markdown: per output, records equal / total and every differing field."""
    lines = [f"# {case['program']} -- COBOL vs Java ({report['java']})", "",
             f"Case `{case['name']}`: {case['corpus']} `{case['program_source']}`, job {case.get('job')} step "
             f"{case.get('step')}, PARM `{case.get('parm')}`, clock `{case.get('clock')}`.", "",
             "| output | records equal | total |", "|---|---|---|"]  # fmt: skip
    for dd, d in report["outputs"].items():
        lines.append(f"| {dd} | {d['equal']} | {d['records']} |")
    for dd, d in report["outputs"].items():
        if d["diffs"]:
            lines += ["", f"## {dd}: differences", "", "| record | field | COBOL | Java |", "|---|---|---|---|"]
            for x in d["diffs"][:200]:
                if x.get("missing"):
                    lines.append(f"| {x['record']} | (record) | {'-' if x['missing'] == 'cobol' else 'present'} | "
                                 f"{'-' if x['missing'] == 'java' else 'present'} |")  # fmt: skip
                for fd in x.get("fields", []):
                    lines.append(f"| {x['record']} | {fd['field']} | `{fd['cobol']}` | `{fd['java']}` |")
    return "\n".join(lines) + "\n"


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
    (corpus_entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(corpus_entry)
    work = args.keep or Path(tempfile.mkdtemp(prefix=f"equiv_{args.case}_"))
    build_image()
    cobol = run_cobol(case, corpus, work / "cobol")
    if args.cobol_only:
        for dd, data in cobol.items():
            print(f"{dd}: {len(data)} bytes, {len(data) // case['datasets'][dd]['reclen']} records")
        return 0
    import equivalence_java as ej

    java = ej.run_java(case, corpus, work / "java", work / "cobol", port=not args.generated_only)
    report: dict[str, Any] = {"case": args.case, "program": case["program"], "outputs": {},
                              "java": "generated" if args.generated_only else "ported"}  # fmt: skip
    ok = True
    for dd, spec in case["datasets"].items():
        if not spec.get("compare"):
            continue
        fields = layout_fields(corpus, spec["copybook"], spec.get("record"))
        d = diff_records(cobol[dd], java.get(dd, b""), spec["reclen"], fields)
        report["outputs"][dd] = d
        ok &= d["equal"] == d["records"] and not d["diffs"]
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (work / "report.md").write_text(report_markdown(case, report), encoding="utf-8")
    for dd, d in report["outputs"].items():
        print(f"{case['program']} {dd}: {d['equal']}/{d['records']} records equal")
        for x in d["diffs"][:10]:
            print(f"   record {x['record']}: {x.get('missing') and 'missing on ' + x['missing'] or x['fields'][:4]}")
    print(f"report: {work / 'report.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
