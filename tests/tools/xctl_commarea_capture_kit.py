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
"""The CICS capture kit for XCTL of a LINK caller's COMMAREA (#5060, #4816; register X39).

    python tests/tools/xctl_commarea_capture_kit.py emit OUTDIR
    python tests/tools/xctl_commarea_capture_kit.py verdict SYSOUT

IBM's XCTL page says the contents of the data area are passed, and is silent on whether the target addresses the
sender's storage or a copy. When a LINKed program XCTLs with (part of) its own DFHCOMMAREA, that decides whether the
target's writes reach the LINK caller. The engine REFUSES the case (X39) until a real CICS run settles it.

`emit` writes three CICS COBOL programs: GGXDRV LINKs to GGXMID three times, once per case, each with its own 20-byte
COMMAREA; GGXMID writes MID into the area and XCTLs to GGXTGT passing the whole DFHCOMMAREA (case W), a group inside
it (case P) or an alias made with SET ADDRESS OF (case A); GGXTGT writes TGT at the start of what it received and
RETURNs, which returns to GGXDRV. GGXDRV DISPLAYs and SENDs `X39-<case>|<area>` for each case.

`verdict` reads that output. MID in the area is the control (a LINKed program's writes are its caller's, IBM). TGT at
the start of the XCTLed area means the target addressed the caller's storage; its absence means a copy. Any other
area (an ERR from a failed XCTL, a missing line, a changed byte) is `invalid`, never a guess. The verdict is
evidence for register X39 only: the refusal in both runtimes is replaced by a model after a person reads the run,
not by this tool.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LEN = 20
FILL = "."
# case -> (what GGXMID passes, offset of the passed area inside the 20 bytes, its length)
CASES = {"W": ("DFHCOMMAREA", 0, LEN), "P": ("CA-PART", 6, 8), "A": ("ALIAS-AREA", 0, LEN)}
CONTROL = ("MID", 9)  # written by GGXMID inside the passed area for P (bytes 10-12)
TARGET = "TGT"


def _line(text: str = "", area_b: bool = False) -> str:
    return " " * (11 if area_b else 7) + text if text else ""


def _src(rows: list[str]) -> str:
    out = [_line(r[2:], r[0] == "B") if r else "" for r in rows]
    assert all(len(line) <= 72 for line in out)
    return "\n".join(out) + "\n"


def emit_driver() -> str:
    rows = [
        "A IDENTIFICATION DIVISION.",
        "A PROGRAM-ID. GGXDRV.",
        "A DATA DIVISION.",
        "A WORKING-STORAGE SECTION.",
        "A 01 WS-CA PIC X(20).",
        "A 01 WS-LINE PIC X(26).",
        "A PROCEDURE DIVISION.",
    ]
    for case in CASES:
        rows += [
            f"B MOVE ALL '{FILL}' TO WS-CA",
            f"B MOVE '{case}' TO WS-CA(1:1)",
            "B EXEC CICS LINK PROGRAM('GGXMID')",
            f"B     COMMAREA(WS-CA) LENGTH({LEN})",
            "B END-EXEC",
            f"B STRING 'X39-{case}|' WS-CA DELIMITED BY SIZE",
            "B     INTO WS-LINE",
            "B DISPLAY WS-LINE",
            "B EXEC CICS SEND TEXT FROM(WS-LINE) LENGTH(26)",
            "B     ACCUM",
            "B END-EXEC",
        ]
    rows += ["B EXEC CICS SEND PAGE END-EXEC", "B EXEC CICS RETURN END-EXEC."]
    return _src(rows)


def emit_middle() -> str:
    rows = [
        "A IDENTIFICATION DIVISION.",
        "A PROGRAM-ID. GGXMID.",
        "A DATA DIVISION.",
        "A WORKING-STORAGE SECTION.",
        "A 01 WS-RESP PIC S9(8) COMP.",
        "A LINKAGE SECTION.",
        "A 01 DFHCOMMAREA.",
        "B 05 CA-HEAD PIC X(6).",
        "B 05 CA-PART PIC X(8).",
        "B 05 CA-TAIL PIC X(6).",
        "A 01 ALIAS-AREA PIC X(20).",
        "A PROCEDURE DIVISION.",
        f"B MOVE '{CONTROL[0]}' TO CA-PART(4:3)",
        "B SET ADDRESS OF ALIAS-AREA TO ADDRESS OF DFHCOMMAREA",
        "B EVALUATE CA-HEAD(1:1)",
    ]
    for case, (name, _off, length) in CASES.items():
        rows += [
            f"B WHEN '{case}'",
            "B     EXEC CICS XCTL PROGRAM('GGXTGT')",
            f"B         COMMAREA({name}) LENGTH({length})",
            "B         RESP(WS-RESP)",
            "B     END-EXEC",
        ]
    rows += [
        "B END-EVALUATE",
        "B MOVE 'ERR' TO CA-TAIL(1:3)",
        "B EXEC CICS RETURN END-EXEC.",
    ]
    return _src(rows)


def emit_target() -> str:
    return _src(
        [
            "A IDENTIFICATION DIVISION.",
            "A PROGRAM-ID. GGXTGT.",
            "A DATA DIVISION.",
            "A LINKAGE SECTION.",
            "A 01 DFHCOMMAREA.",
            "B 05 TGT-HEAD PIC X(3).",
            "A PROCEDURE DIVISION.",
            f"B MOVE '{TARGET}' TO TGT-HEAD",
            "B EXEC CICS RETURN END-EXEC.",
        ]
    )


def readme() -> str:
    return """# XCTL of a LINK caller's COMMAREA: the CICS capture (#5060, register X39)

1. Compile GGXDRV.cbl, GGXMID.cbl and GGXTGT.cbl with the CICS translator, and DEFINE PROGRAM(GGXDRV),
   PROGRAM(GGXMID) and PROGRAM(GGXTGT) LANGUAGE(COBOL), plus TRANSACTION(GGXD) PROGRAM(GGXDRV).
2. Run GGXD once on a terminal. Save the three `X39-W|`, `X39-P|` and `X39-A|` lines (the terminal text or the
   region's SYSOUT) into one file.
3. `python tests/tools/xctl_commarea_capture_kit.py verdict FILE`.

Record the CICS release and the file's sha256 with the verdict in register X39. Nothing here changes the engine:
the refusal stays until a person replaces it with a model.
"""


def emit(outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    files = {
        "GGXDRV.cbl": emit_driver(),
        "GGXMID.cbl": emit_middle(),
        "GGXTGT.cbl": emit_target(),
        "README.md": readme(),
    }
    for name, text in files.items():
        (outdir / name).write_text(text, encoding="utf-8", newline="\n")
    return [outdir / n for n in files]


def expected_area(case: str, same: bool) -> str:
    """The 20 bytes GGXDRV shows for a case under the same-storage (True) or copy (False) hypothesis."""
    _name, off, _length = CASES[case]
    area = list(case + FILL * (LEN - 1))
    area[CONTROL[1] : CONTROL[1] + 3] = CONTROL[0]
    if same:
        area[off : off + 3] = TARGET
    return "".join(area)


def parse_output(text: str) -> dict[str, str]:
    """case -> the 20-byte area of its `X39-<case>|<area>` line (the last one wins; text around a line is ignored)."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        for case in CASES:
            tag = f"X39-{case}|"
            if tag in line:
                found[case] = line.split(tag, 1)[1][:LEN].ljust(LEN)
    return found


def judge(text: str) -> dict[str, str]:
    """case -> `same-storage`, `copy` or `invalid`; plus `overall` (agreement, `mixed`, or `invalid`)."""
    areas = parse_output(text)
    out: dict[str, str] = {}
    for case in CASES:
        got = areas.get(case)
        if got == expected_area(case, True):
            out[case] = "same-storage"
        elif got == expected_area(case, False):
            out[case] = "copy"
        else:
            out[case] = "invalid"
    kinds = set(out.values())
    out["overall"] = kinds.pop() if len(kinds) == 1 else ("invalid" if "invalid" in kinds else "mixed")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emit")
    e.add_argument("outdir", type=Path)
    v = sub.add_parser("verdict")
    v.add_argument("sysout", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "emit":
        for p in emit(args.outdir):
            print(p)
        return 0
    res = judge(args.sysout.read_text(encoding="utf-8"))
    for k, val in res.items():
        print(f"{k}: {val}")
    return 0 if res["overall"] in ("same-storage", "copy") else 1


if __name__ == "__main__":
    sys.exit(main())
