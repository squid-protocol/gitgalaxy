#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The z/OS capture kit for IBM hexadecimal floating point (#4271, #4050; register C6).

    python tests/tools/hfp_capture_kit.py emit   OUTDIR
    python tests/tools/hfp_capture_kit.py ingest SYSOUT --job JOB --step STEP --calibrated-under OPTIONS.json [--kit asm] [--table T]
    python tests/tools/hfp_capture_kit.py verify SYSOUT [--kit asm] [--table T]

`emit` writes HFPCAP.cbl and HFPCAP.jcl from the `ibm-publication` records of zos_captures/hfp.json: a program that
runs each record's operation on z/OS and DISPLAYs `id|result`. `ingest` reads the job's output and appends one
`zos-run` record per captured line, with its evidence (job, step, the output's sha256; never the data) and the runtime
options it ran under (`runtime_options.calibration_problems`). A record that exists is never rewritten. A model that
disagrees with a captured result is reported as a finding against the model: the record stays, the model is fixed.
`emit` also writes HFPCAPA.asm / HFPCAPA.jcl, the High Level Assembler kit for the records COBOL cannot ask (below);
`--kit asm` ingests or verifies that job's output instead of HFPCAP's. `verify` is `ingest` as a dry run: it needs no job, step or options, appends nothing, and prints the same report, so
the findings are seen before a record is committed.

Not every record can be asked of a COBOL program, and the kit says which are skipped and why (`SKIPPED`): COBOL has
no IEEE converter (from_ieee / to_ieee), and a short multiply or divide is evaluated by IBM in long floating point and
rounded, which is not the short arithmetic the table's short rows state; the same for a short `**` (`pow`).

The records skipped above are asked by HFPCAPA, a High Level Assembler program (OPTABLE(UNI)): the IEEE conversions with
the CONVERT HFP/BFP instructions (THDER / THDR, TBEDR / TBDR, round to nearest even) and the short multiply and divide
with MEER and DER, which are the short arithmetic itself. It prints the same `id|HEX` lines. A short `pow` stays
unasked. The assembler source cannot be assembled by the tests: they hold its text and the ingest of model-computed
output, so the first z/OS assembly may need a syntax fix, which changes no record.

`pow` is `COMPUTE LR = LA ** LB` (DBB EPSMPMT's `(1 + C) ** WS-NUMBER-OF-MONTHS`, the one float hole left in
`mortgage-mpmt`): IBM documents no result for it, so a `pow` record is a `model-assumption` whose `want` is `power()`,
the kit's own reference. It is evidence of nothing until a z/OS run agrees; a disagreement is a finding against the
reference, and the det translator keeps refusing a float `**`.

A `model-assumption` record states what the det runtime ASSUMES where IBM documents nothing (register C6, ASSUMED): a
fixed-point value converted to float is truncated to long, a float result stored in a fixed-point receiver truncates
unless ROUNDED (`store`), DISPLAY's mantissa is rounded. It is asked like a publication record, but its `want` is the
model's own answer, never IBM's: it is evidence of nothing until a z/OS run agrees, and the z/OS result then decides.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import ROUND_DOWN, Context, Decimal
from fractions import Fraction as F
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.runtime_options import calibration_problems  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import hfp as H  # noqa: E402

TABLE = REPO_ROOT / "tests" / "cobol_mainframe" / "zos_captures" / "hfp.json"
SOURCES = ("ibm-publication", "model-assumption", "zos-run")
ASKED_SOURCES = ("ibm-publication", "model-assumption")  # a z/OS run is asked for both; only the first is IBM's word
OPS = {
    "encode": ("value",),
    "add": ("a", "b"),
    "sub": ("a", "b"),
    "mul": ("a", "b"),
    "div": ("a", "b"),
    "display": ("a",),
    "fixed": ("a", "scale"),
    "store": ("a", "b", "arith", "scale"),
    "from_ieee": ("a",),
    "to_ieee": ("a",),
    "round_short": ("a",),
    "compare": ("a", "b"),
    "pow": ("a", "b"),
}
FUNC = {"add": H.add, "sub": H.sub, "mul": H.mul, "div": H.div}
ARITH = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
ARITH_NAME = {v: k for k, v in ARITH.items()}
SKIP_IEEE = "COBOL has no IEEE converter"
POW_PRECISION = 60  # decimal digits of the reference for a fractional exponent; far past the 14 hex digits it is cut to
SKIP_SHORT = "IBM evaluates a COMP-1 multiply, divide or exponentiation in long floating point, not the short arithmetic the row states"


def records(table: Path | None = None) -> list[dict]:
    return json.loads((table or TABLE).read_text(encoding="utf-8"))["records"]


def power(base: F, exp: F) -> F:
    """The kit's REFERENCE for `base ** exp` in long HFP: the exact power truncated to long (an integer exponent), or
    exp(exp * ln(base)) at POW_PRECISION digits truncated to long. IBM documents no result (register C6), so this is
    an assumption the z/OS run decides, not a model the det runtime uses (it still refuses a float `**`)."""
    if exp.denominator == 1:
        return H.of(base**exp.numerator if exp >= 0 else 1 / base ** (-exp.numerator))
    if base <= 0:
        raise ValueError("a fractional exponent needs a positive base")
    ctx = Context(prec=POW_PRECISION)
    value = ctx.exp(ctx.multiply(H._dec(exp), ctx.ln(H._dec(base))))
    return H.of(F(value))


def compute(r: dict) -> str:
    """The model's answer for a record (hex for the byte ops, text for display, a decimal for fixed)."""
    short = r["size"] == "short"
    if r["op"] == "encode":
        return H.encode(H.for_item(F(r["value"]), short), short).hex().upper()
    if r["op"] == "from_ieee":
        return H.from_ieee(int(r["a"], 16), 4 if short else 8).hex().upper()
    if r["op"] == "to_ieee":
        return f"{H.to_ieee(bytes.fromhex(r['a'])):0{8 if short else 16}X}"
    if r["op"] == "round_short":  # a long item MOVEd to a COMP-1: LOAD ROUNDED (a is the long hex, the result short)
        return H.encode(H.to_short(H.decode(bytes.fromhex(r["a"]))), True).hex().upper()
    a = H.decode(bytes.fromhex(r["a"]))
    if r["op"] == "pow":
        return H.encode(power(a, H.decode(bytes.fromhex(r["b"]))), False).hex().upper()
    if r["op"] == "compare":
        b = H.decode(bytes.fromhex(r["b"]))
        return "<" if a < b else ">" if a > b else "="
    if r["op"] == "display":
        return H.display(a, not short)
    if r["op"] == "fixed":
        return str(H.to_fixed(a, r["scale"], 9 if short else 18))
    if r["op"] == "store":  # COMPUTE of a fixed-point receiver from long operands (size is long)
        res = FUNC[ARITH_NAME[r["arith"]]](a, H.decode(bytes.fromhex(r["b"])), True)
        if r.get("rounded"):
            return str(H.to_fixed(res, r["scale"], 18))
        q = Decimal(1).scaleb(-r["scale"])
        return str(H._dec(res).quantize(q, rounding=ROUND_DOWN))
    out = FUNC[r["op"]](a, H.decode(bytes.fromhex(r["b"])), not short)
    return H.encode(out, short).hex().upper()


def skip_reason(r: dict) -> str:
    """Why a record cannot be asked of a COBOL program ('' when it can)."""
    if r["op"] in ("from_ieee", "to_ieee"):
        return SKIP_IEEE
    if r["op"] in ("mul", "div", "pow") and r["size"] == "short":
        return SKIP_SHORT
    return ""


def asm_askable(recs: list[dict]) -> list[dict]:
    """The records COBOL skips that HFPCAPA asks: the IEEE conversions and the short multiply / divide."""
    return [r for r in recs if r.get("source") in ASKED_SOURCES and skip_reason(r) and r["op"] != "pow"]


def askable(recs: list[dict], kit: str = "cobol") -> list[dict]:
    if kit == "asm":
        return asm_askable(recs)
    return [r for r in recs if r.get("source") in ASKED_SOURCES and not skip_reason(r)]


def skipped(recs: list[dict], kit: str = "cobol") -> dict[str, str]:
    """The records a kit cannot ask, with why (for `asm`: those neither kit asks)."""
    left = {r["id"] for r in asm_askable(recs)} if kit == "asm" else set()
    return {
        r["id"]: skip_reason(r)
        for r in recs
        if r.get("source") in ASKED_SOURCES and skip_reason(r) and r["id"] not in left
    }


def _line(text: str) -> str:
    """One fixed-format source line (code in columns 8-72)."""
    body = "       " + text
    if len(body) > 72:
        raise ValueError(f"line past column 72: {text}")
    return body


def _cobol_literal(value: str) -> str:
    if not re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", value):  # a malformed value fails here, not on z/OS
        raise ValueError(f"not a plain decimal literal: {value}")
    return value


def statements(r: dict) -> list[str]:
    """The COBOL for one record: set the operands, run the operation, DISPLAY `id|result`."""
    p = "S" if r["size"] == "short" else "L"
    tag = f'"{r["id"]}|"'
    op = r["op"]
    out = []
    if op == "round_short":
        out += [f"MOVE X'{r['a']}' TO LA-X", "MOVE LA TO SR", f"DISPLAY {tag} FUNCTION HEX-OF(SR-X)"]
        return [_line(s) for s in out]
    if op == "encode":
        out.append(f"MOVE {_cobol_literal(r['value'])} TO {p}R")
        out.append(f"DISPLAY {tag} FUNCTION HEX-OF({p}R-X)")
        return [_line(s) for s in out]
    out.append(f"MOVE X'{r['a']}' TO {p}A-X")
    if op == "display":
        out.append(f"DISPLAY {tag} {p}A")
    elif op == "compare":
        out.append(f"MOVE X'{r['b']}' TO {p}B-X")
        out += [f'IF {p}A {sign} {p}B DISPLAY {tag} "{sign}" END-IF' for sign in "<=>"]
    elif op == "fixed":
        out.append(f"MOVE {p}A TO E{r['scale']}")
        out.append(f"DISPLAY {tag} E{r['scale']}")
    elif op == "store":
        out.append(f"MOVE X'{r['b']}' TO {p}B-X")
        out.append(f"COMPUTE Q{r['scale']} {'ROUNDED ' if r.get('rounded') else ''}= {p}A {r['arith']} {p}B")
        out.append(f"MOVE Q{r['scale']} TO E{r['scale']}")
        out.append(f"DISPLAY {tag} E{r['scale']}")
    else:
        out.append(f"MOVE X'{r['b']}' TO {p}B-X")
        out.append(f"COMPUTE {p}R = {p}A {'**' if op == 'pow' else ARITH[op]} {p}B")
        out.append(f"DISPLAY {tag} FUNCTION HEX-OF({p}R-X)")
    return [_line(s) for s in out]


def edited_fields(recs: list[dict]) -> list[str]:
    """One numeric-edited receiver (and, for `store`, a numeric one) per scale used (digits before the point: 18 - scale)."""
    lines = []
    for s in sorted({r["scale"] for r in recs if r["op"] in ("fixed", "store")}):
        pic = f"-9({18 - s})" + (f".9({s})" if s else "")
        lines.append(_line(f"01  E{s} PIC {pic}."))
        if any(r["op"] == "store" and r["scale"] == s for r in recs):
            lines.append(_line(f"01  Q{s} PIC S9({18 - s})" + (f"V9({s})." if s else ".")))
    return lines


def emit_program(recs: list[dict]) -> str:
    asked = askable(recs)
    head = [
        _line("IDENTIFICATION DIVISION."),
        _line("PROGRAM-ID. HFPCAP."),
        "      * Generated by hfp_capture_kit.py from zos_captures/hfp.json.",
        "      * Needs Enterprise COBOL 6.3 or later (FUNCTION HEX-OF).",
        _line("DATA DIVISION."),
        _line("WORKING-STORAGE SECTION."),
    ]
    for p, usage, width in (("S", "COMP-1", 4), ("L", "COMP-2", 8)):
        for n in "ABR":
            head += [_line(f"01  {p}{n}-X PIC X({width})."), _line(f"01  {p}{n} REDEFINES {p}{n}-X {usage}.")]
    head += edited_fields(asked)
    body = [_line("PROCEDURE DIVISION.")]
    for r in asked:
        body += statements(r)
    body += [_line("GOBACK.")]
    return "\n".join(head + body) + "\n"


def _asm(label: str, op: str = "", operands: str = "") -> str:
    """One High Level Assembler statement (label column 1, operation column 10, operands column 16)."""
    line = f"{label:<9}{op:<6}{operands}".rstrip()
    if len(line) > 71:
        raise ValueError(f"statement past column 71: {line}")
    return line


ASM_LOAD = {"short": "LE", "long": "LD"}
ASM_STORE = {"short": "STE", "long": "STD"}


def asm_statements(r: dict, n: int) -> list[str]:
    """The assembler for one record: load the operand(s), run the instruction, print `id|HEX` through HEXOUT."""
    size, op = r["size"], r["op"]
    ld, st = ASM_LOAD[size], ASM_STORE[size]
    out = [_asm("", "MVC", "LINE,BLANKS"), _asm("", "MVC", f"LINE({len(r['id']) + 1}),=C'{r['id']}|'")]
    if op == "from_ieee":  # THDER: short BFP to long HFP; THDR: long BFP to long HFP
        out += [
            _asm("", ld, f"0,A{n:03d}"),
            _asm("", "THDER" if size == "short" else "THDR", "2,0"),
            _asm("", "STD", "2,RES"),
        ]
    elif op == "to_ieee":  # TBEDR / TBDR: long HFP to short / long BFP, M3=4 rounds to nearest, ties to even
        out += [
            _asm("", ld, f"0,A{n:03d}"),
            _asm("", "TBEDR" if size == "short" else "TBDR", "2,4,0"),
            _asm("", st, "2,RES"),
        ]
    elif op in ("mul", "div") and size == "short":
        out += [_asm("", "LE", f"0,A{n:03d}"), _asm("", "LE", f"2,B{n:03d}")]
        out += [_asm("", "MEER" if op == "mul" else "DER", "0,2"), _asm("", "STE", "0,RES")]
    else:
        raise ValueError(f"HFPCAPA cannot ask {r['id']} ({op}, {size})")
    out += [
        _asm("", "LA", f"3,LINE+{len(r['id']) + 1}"),
        _asm("", "LA", "2,RES"),
        _asm("", "LA", f"4,{1 if size == 'short' else 2}"),
    ]
    out += [_asm("", "BAS", "14,HEXOUT"), _asm("", "PUT", "SYSPRINT,LINE")]
    return out


def emit_asm(recs: list[dict]) -> str:
    asked = asm_askable(recs)
    head = [
        "*PROCESS OPTABLE(UNI)",
        "* Generated by hfp_capture_kit.py from zos_captures/hfp.json.",
        "* Asks what HFPCAP (COBOL) cannot: IEEE conversions, short MEER / DER.",
        _asm("HFPCAPA", "CSECT"),
        _asm("HFPCAPA", "AMODE", "31"),
        _asm("HFPCAPA", "RMODE", "ANY"),
        _asm("", "YREGS"),
        _asm("", "STM", "14,12,12(13)"),
        _asm("", "LR", "12,15"),
        _asm("", "LA", "11,4095(,12)"),  # a second base: the program can pass 4096 bytes
        _asm("", "LA", "11,1(,11)"),
        _asm("", "USING", "HFPCAPA,12,11"),
        _asm("", "LA", "2,SAVE"),
        _asm("", "ST", "13,4(,2)"),
        _asm("", "ST", "2,8(,13)"),
        _asm("", "LR", "13,2"),
        _asm("", "OPEN", "(SYSPRINT,(OUTPUT))"),
    ]
    body: list[str] = []
    data: list[str] = []
    for n, r in enumerate(asked, 1):
        body += asm_statements(r, n)
        data.append(_asm(f"A{n:03d}", "DC", f"XL8'{r['a'].ljust(16, '0')}'"))
        if r["op"] in ("mul", "div"):
            data.append(_asm(f"B{n:03d}", "DC", f"XL8'{r['b'].ljust(16, '0')}'"))
    tail = [
        _asm("", "CLOSE", "(SYSPRINT)"),
        _asm("", "L", "13,4(,13)"),
        _asm("", "LM", "14,12,12(13)"),
        _asm("", "SLR", "15,15"),
        _asm("", "BR", "14"),
        _asm("HEXOUT", "DS", "0H"),
        _asm("HEXLP", "MVC", "W(4),0(2)"),
        _asm("", "UNPK", "P(9),W(5)"),
        _asm("", "TR", "P(8),HEXTAB-240"),
        _asm("", "MVC", "0(8,3),P"),
        _asm("", "LA", "2,4(,2)"),
        _asm("", "LA", "3,8(,3)"),
        _asm("", "BCT", "4,HEXLP"),
        _asm("", "BR", "14"),
        _asm("", "LTORG"),
        _asm("", "DS", "0D"),
    ]
    tail += data
    tail += [
        _asm("RES", "DS", "XL8"),
        _asm("W", "DS", "XL5"),
        _asm("P", "DS", "CL9"),
        _asm("LINE", "DS", "CL80"),
        _asm("BLANKS", "DC", "CL80' '"),
        _asm("HEXTAB", "DC", "C'0123456789ABCDEF'"),
        _asm("SAVE", "DS", "18F"),
        _asm("SYSPRINT", "DCB", "DDNAME=SYSPRINT,DSORG=PS,MACRF=PM,RECFM=FB,LRECL=80"),
        _asm("", "END"),
    ]
    return "\n".join(head + body + tail) + "\n"


def emit_asm_jcl() -> str:
    return (
        "//HFPCAPA  JOB (ACCT),'HFP CAPTURE ASM',CLASS=A,MSGCLASS=H\n"
        "//* Assemble, link and run HFPCAPA; keep the G step's SYSPRINT for `hfp_capture_kit.py ingest --kit asm`.\n"
        "//* Edit the procedure name and data sets to the site's. Records no customer data.\n"
        "//ASM      EXEC ASMACLG\n"
        "//C.SYSIN DD DISP=SHR,DSN=&SYSUID..HFPCAPA.ASM\n"
        "//G.SYSPRINT DD SYSOUT=*\n"
    )


def emit_jcl() -> str:
    return (
        "//HFPCAP   JOB (ACCT),'HFP CAPTURE',CLASS=A,MSGCLASS=H\n"
        "//* Compile, link and run HFPCAP; keep the job's SYSOUT for `hfp_capture_kit.py ingest`.\n"
        "//* Edit the procedure name and data sets to the site's. Records no customer data.\n"
        "//COB      EXEC IGYWCLG\n"
        "//COBOL.SYSIN DD DISP=SHR,DSN=&SYSUID..HFPCAP.CBL\n"
        "//GO.SYSOUT DD SYSOUT=*\n"
    )


def parse_output(text: str, ids: set[str]) -> dict[str, str]:
    """`id|result` lines of the job's output, for the ids asked (the result text keeps its leading space)."""
    got: dict[str, str] = {}
    for line in text.splitlines():
        ident, sep, rest = line.partition("|")
        if sep and ident.strip() in ids:
            got[ident.strip()] = rest.rstrip()
    return got


def captured_record(r: dict, result: str, evidence: dict, under: dict) -> dict:
    rec = {k: v for k, v in r.items() if k not in ("id", "source", "want")}
    return {
        "id": "zos-" + r["id"],
        "source": "zos-run",
        **rec,
        "want": result,
        "evidence": evidence,
        "calibrated_under": under,
    }


def ingest(text: str, table: Path, job: str, step: str, under: dict, dry_run: bool = False, kit: str = "cobol") -> dict:
    """Append the captured records; returns {'added': ids, 'findings': [...], 'missing': ids, 'skipped': ids}.

    `dry_run` reports the same result (`added` is what would be appended) without the evidence check or a write."""
    problems = calibration_problems(under)
    if not dry_run and (problems or not job or not step):
        raise ValueError("; ".join(problems + ([] if job and step else ["job and step are required evidence"])))
    recs = records(table)
    asked = {r["id"]: r for r in askable(recs, kit)}
    have = {r["id"] for r in recs}
    got = parse_output(text, set(asked))
    evidence = {"job": job, "step": step, "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    new, findings, kept = [], [], []
    for ident, raw in got.items():
        result = raw if asked[ident]["op"] == "display" else raw.strip()
        rec = captured_record(asked[ident], result, evidence, under)
        if rec["id"] in have:
            kept.append(rec["id"])
            continue
        new.append(rec)
        model = compute(rec)
        same = Decimal(model) == Decimal(result) if rec["op"] in ("fixed", "store") else model == result
        if not same:
            findings.append(f"{rec['id']}: model {model!r}, z/OS {result!r}: a finding against the model")
    if new and not dry_run:
        _append(table, new)
    return {
        "added": [r["id"] for r in new],
        "findings": findings,
        "kept": kept,
        "missing": sorted(set(asked) - set(got)),
        "skipped": skipped(recs, kit),
    }


def _append(table: Path, new: list[dict]) -> None:
    """Splice the records in before the closing bracket, leaving every existing line as it is."""
    text = table.read_text(encoding="utf-8")
    cut = text.rindex("\n  ]")
    lines = ",\n".join("    " + json.dumps(r, ensure_ascii=True) for r in new)
    table.write_text(text[:cut] + ",\n" + lines + text[cut:], encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("outdir", type=Path)
    i = sub.add_parser("ingest")
    i.add_argument("sysout", type=Path)
    i.add_argument("--job", required=True)
    i.add_argument("--step", required=True)
    i.add_argument("--calibrated-under", type=Path, required=True)
    i.add_argument("--table", type=Path, default=TABLE)
    i.add_argument("--kit", choices=("cobol", "asm"), default="cobol")
    v = sub.add_parser("verify")
    v.add_argument("sysout", type=Path)
    v.add_argument("--table", type=Path, default=TABLE)
    v.add_argument("--kit", choices=("cobol", "asm"), default="cobol")
    a = ap.parse_args(argv)
    if a.cmd == "emit":
        a.outdir.mkdir(parents=True, exist_ok=True)
        recs = records()
        (a.outdir / "HFPCAP.cbl").write_text(emit_program(recs), encoding="utf-8")
        (a.outdir / "HFPCAP.jcl").write_text(emit_jcl(), encoding="utf-8")
        (a.outdir / "HFPCAPA.asm").write_text(emit_asm(recs), encoding="utf-8")
        (a.outdir / "HFPCAPA.jcl").write_text(emit_asm_jcl(), encoding="utf-8")
        print(
            f"asked {len(askable(recs))} records (HFPCAP) + {len(asm_askable(recs))} (HFPCAPA); SKIPPED {len(skipped(recs, 'asm'))}: {sorted(set(skipped(recs, 'asm').values()))}"
        )
        return 0
    if a.cmd == "verify":
        res = ingest(a.sysout.read_text(encoding="utf-8"), a.table, "", "", {}, dry_run=True, kit=a.kit)
        print(json.dumps(res, indent=1))
        return 1 if res["findings"] else 0
    under = json.loads(a.calibrated_under.read_text(encoding="utf-8"))
    res = ingest(a.sysout.read_text(encoding="utf-8"), a.table, a.job, a.step, under, kit=a.kit)
    print(json.dumps(res, indent=1))
    return 1 if res["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
