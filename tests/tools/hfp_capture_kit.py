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
    python tests/tools/hfp_capture_kit.py ingest SYSOUT --job JOB --step STEP --calibrated-under OPTIONS.json [--table T]

`emit` writes HFPCAP.cbl and HFPCAP.jcl from the `ibm-publication` records of zos_captures/hfp.json: a program that
runs each record's operation on z/OS and DISPLAYs `id|result`. `ingest` reads the job's output and appends one
`zos-run` record per captured line, with its evidence (job, step, the output's sha256; never the data) and the runtime
options it ran under (`runtime_options.calibration_problems`). A record that exists is never rewritten. A model that
disagrees with a captured result is reported as a finding against the model: the record stays, the model is fixed.

Not every record can be asked of a COBOL program, and the kit says which are skipped and why (`SKIPPED`): COBOL has
no IEEE converter (from_ieee / to_ieee), and a short multiply or divide is evaluated by IBM in long floating point and
rounded, which is not the short arithmetic the table's short rows state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.runtime_options import calibration_problems  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import hfp as H  # noqa: E402

TABLE = REPO_ROOT / "tests" / "cobol_mainframe" / "zos_captures" / "hfp.json"
SOURCES = ("ibm-publication", "zos-run")
OPS = {
    "encode": ("value",),
    "add": ("a", "b"),
    "sub": ("a", "b"),
    "mul": ("a", "b"),
    "div": ("a", "b"),
    "display": ("a",),
    "fixed": ("a", "scale"),
    "from_ieee": ("a",),
    "to_ieee": ("a",),
}
FUNC = {"add": H.add, "sub": H.sub, "mul": H.mul, "div": H.div}
ARITH = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
SKIP_IEEE = "COBOL has no IEEE converter"
SKIP_SHORT = "IBM evaluates a COMP-1 multiply or divide in long floating point, not the short arithmetic the row states"


def records(table: Path | None = None) -> list[dict]:
    return json.loads((table or TABLE).read_text(encoding="utf-8"))["records"]


def compute(r: dict) -> str:
    """The model's answer for a record (hex for the byte ops, text for display, a decimal for fixed)."""
    short = r["size"] == "short"
    if r["op"] == "encode":
        return H.encode(H.for_item(F(r["value"]), short), short).hex().upper()
    if r["op"] == "from_ieee":
        return H.from_ieee(int(r["a"], 16), 4 if short else 8).hex().upper()
    if r["op"] == "to_ieee":
        return f"{H.to_ieee(bytes.fromhex(r['a'])):0{8 if short else 16}X}"
    a = H.decode(bytes.fromhex(r["a"]))
    if r["op"] == "display":
        return H.display(a, not short)
    if r["op"] == "fixed":
        return str(H.to_fixed(a, r["scale"], 9 if short else 18))
    out = FUNC[r["op"]](a, H.decode(bytes.fromhex(r["b"])), not short)
    return H.encode(out, short).hex().upper()


def skip_reason(r: dict) -> str:
    """Why a record cannot be asked of a COBOL program ('' when it can)."""
    if r["op"] in ("from_ieee", "to_ieee"):
        return SKIP_IEEE
    if r["op"] in ("mul", "div") and r["size"] == "short":
        return SKIP_SHORT
    return ""


def askable(recs: list[dict]) -> list[dict]:
    return [r for r in recs if r.get("source") == "ibm-publication" and not skip_reason(r)]


def skipped(recs: list[dict]) -> dict[str, str]:
    return {r["id"]: skip_reason(r) for r in recs if r.get("source") == "ibm-publication" and skip_reason(r)}


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
    if op == "encode":
        out.append(f"MOVE {_cobol_literal(r['value'])} TO {p}R")
        out.append(f"DISPLAY {tag} FUNCTION HEX-OF({p}R-X)")
        return [_line(s) for s in out]
    out.append(f"MOVE X'{r['a']}' TO {p}A-X")
    if op == "display":
        out.append(f"DISPLAY {tag} {p}A")
    elif op == "fixed":
        out.append(f"MOVE {p}A TO E{r['scale']}")
        out.append(f"DISPLAY {tag} E{r['scale']}")
    else:
        out.append(f"MOVE X'{r['b']}' TO {p}B-X")
        out.append(f"COMPUTE {p}R = {p}A {ARITH[op]} {p}B")
        out.append(f"DISPLAY {tag} FUNCTION HEX-OF({p}R-X)")
    return [_line(s) for s in out]


def edited_fields(recs: list[dict]) -> list[str]:
    """One numeric-edited receiver per scale a `fixed` record uses (digits before the point: 18 - scale)."""
    lines = []
    for s in sorted({r["scale"] for r in recs if r["op"] == "fixed"}):
        pic = f"-9({18 - s})" + (f".9({s})" if s else "")
        lines.append(_line(f"01  E{s} PIC {pic}."))
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


def ingest(text: str, table: Path, job: str, step: str, under: dict) -> dict:
    """Append the captured records; returns {'added': ids, 'findings': [...], 'missing': ids, 'skipped': ids}."""
    problems = calibration_problems(under)
    if problems or not job or not step:
        raise ValueError("; ".join(problems + ([] if job and step else ["job and step are required evidence"])))
    recs = records(table)
    asked = {r["id"]: r for r in askable(recs)}
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
        same = Decimal(model) == Decimal(result) if rec["op"] == "fixed" else model == result
        if not same:
            findings.append(f"{rec['id']}: model {model!r}, z/OS {result!r}: a finding against the model")
    if new:
        _append(table, new)
    return {
        "added": [r["id"] for r in new],
        "findings": findings,
        "kept": kept,
        "missing": sorted(set(asked) - set(got)),
        "skipped": skipped(recs),
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
    a = ap.parse_args(argv)
    if a.cmd == "emit":
        a.outdir.mkdir(parents=True, exist_ok=True)
        recs = records()
        (a.outdir / "HFPCAP.cbl").write_text(emit_program(recs), encoding="utf-8")
        (a.outdir / "HFPCAP.jcl").write_text(emit_jcl(), encoding="utf-8")
        skips = skipped(recs)
        print(f"asked {len(askable(recs))} records; SKIPPED {len(skips)}: {sorted(set(skips.values()))}")
        return 0
    under = json.loads(a.calibrated_under.read_text(encoding="utf-8"))
    res = ingest(a.sysout.read_text(encoding="utf-8"), a.table, a.job, a.step, under)
    print(json.dumps(res, indent=1))
    return 1 if res["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
