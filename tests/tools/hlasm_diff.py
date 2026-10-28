"""#5859 slice 6: a per-instruction differential. Each snippet runs through the independent POPS interpreter
(hlasm_interp.py) and, lowered by det/hlasm.py, through GnuCOBOL in the pinned oracle image; the registers and the
numeric storage cells it leaves must agree. One docker run builds and runs every snippet."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_oracle  # noqa: E402
import hlasm_interp as H  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import hlasm  # noqa: E402

PRELUDE = [
    "DFHEISTG DSECT",
    "W_A      DS    CL4",
    "W_H      DS    H",
    "W_F      DS    F",
    "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11",
]
ENDING = [f"R{n}       EQU   {n}" for n in (2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14)] + ["         END   PROG"]
OBSERVED = (2, 3, 4, 5, 6, 7)
RETURN = "         EXEC CICS RETURN"


def big(reg: int, value: int) -> list[str]:
    """Load `value` (0..2**31-1) into `reg` with LA / SLL / LA-free arithmetic the subset owns."""
    return [
        f"         LA    R{reg},{value >> 20}",
        f"         SLL   R{reg},20",
        f"         LA    R{reg + 1},{value & 0xFFF}",
    ]


def cases() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for v in (0, 1, 4095):
        out[f"la-{v}"] = [f"         LA    R2,{v}", "         LA    R3,1(,R2)", "         LA    R4,4095(,R2)"]
    for v in (0, 1, 7, 4095):
        for k in (0, 1, 11, 20, 31):
            out[f"sll-{v}-{k}"] = [f"         LA    R2,{v}", f"         SLL   R2,{k}"]
    for v in (0, 1, 4095):
        for k in (1, 5, 31):
            out[f"sldl-{v}-{k}"] = [f"         LA    R2,{v}", "         LA    R3,4095", f"         SLDL  R2,{k}"]
    out["sr-self"] = ["         LA    R2,77", "         SR    R2,R2"]
    out["bct-loop"] = ["         LA    R3,5", "         LA    R4,0", "L1       LA    R4,3(,R4)",
                       "         BCT   R3,L1"]  # fmt: skip
    for v in (0, 1, 32767, 32768, 65535):
        out[f"sth-{v}"] = [*big(2, v << 4)[:2], f"         LA    R4,{v & 4095}", "         STH   R4,W_H", "         CH    R4,W_H",
                          "         BC    8,EQ", "         LA    R5,1", "         B     DONE", "EQ       DS    0H",
                          "         LA    R5,2", "DONE     DS    0H"]  # fmt: skip
    for a, b in ((0, 0), (1, 2), (2, 1), (4095, 4095)):
        for mask in (2, 4, 7, 8, 10, 11, 12, 13):
            out[f"ch-{a}-{b}-{mask}"] = [f"         LA    R2,{a}", f"         LA    R3,{b}", "         STH   R3,W_H",
                                         "         CH    R2,W_H", f"         BC    {mask},T", "         LA    R5,1",
                                         "         B     DONE", "T        DS    0H", "         LA    R5,2",
                                         "DONE     DS    0H"]  # fmt: skip
    return out


def source(code: list[str]) -> str:
    return "\n".join([*PRELUDE, *code, RETURN, *ENDING]) + "\n"


def interpret(code: list[str]) -> dict[str, int]:
    res = H.Machine(source(code)).run(b"")
    return {f"R{n}": res.regs[n] % 2**32 for n in OBSERVED}


def lowered(code: list[str]) -> str | None:
    """The COBOL program with its closing EXEC CICS RETURN replaced by a DISPLAY of every register it uses."""
    text = hlasm.lower_text(source(code), "T.asm")
    used = sorted({int(n) for n in re.findall(r"HL-R(\d+) PIC", text)})
    shows = "".join(f'           DISPLAY "R{n}=" HL-R{n}\n' for n in used if n in OBSERVED)
    body, n = re.subn(r"           EXEC CICS\n\s+RETURN END-EXEC\.", shows + "           STOP RUN.", text)
    return body if n == 1 else None


def available() -> str | None:
    try:
        proc = subprocess.run(["docker", "image", "inspect", equivalence_oracle.IMAGE],  # noqa: S603, S607
                              capture_output=True, check=False, timeout=60)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"docker unavailable: {e}"
    return None if proc.returncode == 0 else f"image {equivalence_oracle.IMAGE} not built"


def run_cobol(programs: dict[str, str]) -> dict[str, dict[str, int]]:
    """Compile and run every program in ONE container; the registers each one displays."""
    with tempfile.TemporaryDirectory(prefix="hlasm-diff-") as tmp:
        work = Path(tmp)
        names = {name: f"p{i}" for i, name in enumerate(programs)}
        for name, text in programs.items():
            (work / f"{names[name]}.cbl").write_text(text, encoding="utf-8")
        script = (
            'cd /work; for f in p*.cbl; do b=${f%.cbl}; echo "== $b"; '
            + "cobc -x -std=ibm -fbinary-truncate -o $b $f 2>&1 && ./$b 2>&1; done"
        )
        proc = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/work", equivalence_oracle.IMAGE, "sh", "-c", script],  # noqa: S603, S607
                              capture_output=True, text=True, check=False, timeout=900)  # fmt: skip
    seen: dict[str, dict[str, int]] = {}
    cur = ""
    for line in proc.stdout.splitlines():
        if line.startswith("== "):
            cur = line[3:].strip()
            seen[cur] = {}
        elif m := re.fullmatch(r"(R\d)=([+-]?\d+)", line.strip()):
            seen[cur][m.group(1)] = int(m.group(2)) % 2**32
    by_id = {v: k for k, v in names.items()}
    return {by_id[k]: v for k, v in seen.items()}


def differences() -> list[str]:
    cs = cases()
    progs = {}
    for name, code in cs.items():
        text = lowered(code)
        if text is not None:
            progs[name] = text
    got = run_cobol(progs)
    out = []
    for name, code in cs.items():
        want = interpret(code)
        have = got.get(name)
        if not have:
            out.append(f"{name}: cobc produced no registers")
            continue
        for reg, val in have.items():
            if want[reg] != val:
                out.append(f"{name}: {reg} interpreter {want[reg]} lowering {val}")
    return out
