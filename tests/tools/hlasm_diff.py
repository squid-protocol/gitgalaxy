"""#5859 slice 6: a per-instruction differential. Each snippet runs through the independent POPS interpreter
(hlasm_interp.py) and, lowered by det/hlasm.py, through GnuCOBOL in the pinned oracle image; the registers and the
storage bytes it leaves must agree. One docker run builds and runs every snippet.

Storage bytes (slice 7): a case may name DS fields in `BYTES`. The interpreter's bytes and the lowering's (shown one
`FUNCTION ORD` per byte) are compared raw for binary data (`RAW`), and as characters for text: the interpreter holds
EBCDIC, the lowering ASCII (design doc assumption 3), so a text case keeps to letters, where both encodings order alike."""

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
    "W_B      DS    CL8",
    "W_C      DS    CL8",
    "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11",
]
ENDING = [f"R{n}       EQU   {n}" for n in (2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14)] + ["         END   PROG"]
OBSERVED = (2, 3, 4, 5, 6, 7)
RETURN = "         EXEC CICS RETURN"
DATA = "=DATA"  # in a case: the lines after it are constants placed after the closing RETURN, as the zECS tables are
TABLE = [
    f"{'TBL' if i == 0 else '':<9}DC    XL16'"
    + "".join(f"{(j * 7 + 3 + i * 16 * 7) & 255:02X}" for j in range(16))
    + "'"
    for i in range(16)
]
BYTES: dict[str, tuple[str, ...]] = {}  # case -> the DS fields whose bytes are compared
RAW: set[str] = set()  # the cases whose bytes are binary (compared as they are, not as characters)


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
    out.update(byte_cases())
    return out


def raw_bytes(field: str, values: list[int]) -> list[str]:
    """Store each value (0..255) into `field` byte by byte: LA puts it in the register's low byte, STCM picks it."""
    return [x for i, v in enumerate(values) for x in (f"         LA    R2,{v}", f"         STCM  R2,1,{field}+{i}")]


def word(hi: int, lo: int) -> list[str]:
    """R2 = hi:lo as four bytes (hi, lo are 16-bit): 12 bits, 12 bits, then 8 bits merged through SLDL."""
    a, b, c, d = hi >> 8, hi & 255, lo >> 8, lo & 255
    return [f"         LA    R2,{(a << 4) | (b >> 4)}", f"         LA    R3,{((b & 15) << 8) | c}", "         SLL   R3,20",
            "         SLDL  R2,12", f"         LA    R3,{d}", "         SLL   R3,24", "         SLDL  R2,8"]  # fmt: skip


def _case(name: str, code: list[str], fields: tuple[str, ...], raw: bool) -> tuple[str, list[str]]:
    BYTES[name] = fields
    if raw:
        RAW.add(name)
    return name, code


def byte_cases() -> dict[str, list[str]]:
    """Slice 7: the instructions whose effect is in storage bytes, not registers."""
    out: dict[str, list[str]] = {}

    def add(name: str, code: list[str], fields: tuple[str, ...], raw: bool = False) -> None:
        k, v = _case(name, code, fields, raw)
        out[k] = ["         XC    W_B,W_B", "         XC    W_C,W_C", *v]  # DFHEISTG is unset: zero what is compared

    text = ["         MVC   W_B,=C'ABCDEFGH'"]
    add("mvc-literal", text, ("W_B",))
    for n in (1, 2, 4, 8):
        for k in (0, 1):
            if n + k <= 8:
                add(
                    f"mvc-{n}-{k}",
                    ["         XC    W_C,W_C", *text, f"         MVC   W_C({n}),W_B+{k}"],
                    ("W_B", "W_C"),
                )
    for n in (1, 2, 4, 8):
        add(f"mvc-len-{n}", ["         XC    W_C,W_C", *text, f"         MVC   W_C({n}),W_B"], ("W_C",))
    add("xc-clear", [*text, "         XC    W_B,W_B"], ("W_B",), True)
    for field, size in (
        ("W_H", "H"),
        ("W_F", "F"),
    ):  # OC X,X is a zero test, so the lowering takes only a numeric field
        for v in (0, 1, 4095):
            load = [f"         LA    R2,{v}", f"         ST{'H' if size == 'H' else ''}    R2,{field}"]
            for mask in (8, 7):
                add(f"oc-{field}-{v}-{mask}", [*load, f"         OC    {field},{field}", f"         BC    {mask},T", "         LA    R5,1",
                                               "         B     DONE", "T        DS    0H", "         LA    R5,2", "DONE     DS    0H"], ())  # fmt: skip
    pairs = (("ABCDEFGH", "ABCDEFGH"), ("ABCDEFGH", "ABCDEFGI"), ("ABCDEFGI", "ABCDEFGH"), ("BBCDEFGH", "ABCDEFGH"),
             ("ABCDEFGH", "BBCDEFGH"))  # fmt: skip
    for i, (a, b) in enumerate(pairs):
        for mask in (8, 7):
            add(f"clc-{i}-{mask}", [f"         MVC   W_B,=C'{a}'", f"         MVC   W_C,=C'{b}'", "         CLC   W_B,W_C",
                                    f"         BC    {mask},T", "         LA    R5,1", "         B     DONE", "T        DS    0H",
                                    "         LA    R5,2", "DONE     DS    0H"], ("W_B", "W_C"))  # fmt: skip
    for v in (0x00, 0x40, 0x7E, 0x80, 0xFF):
        for imm in ("X'00'", "X'40'", "X'7E'"):
            for mask in (8, 7):
                add(f"cli-{v:02x}-{imm[2:4]}-{mask}", [*raw_bytes("W_B", [v]), f"         CLI   W_B,{imm}",
                                                       f"         BC    {mask},T", "         LA    R5,1", "         B     DONE",
                                                       "T        DS    0H", "         LA    R5,2", "DONE     DS    0H"], ("W_B",), True)  # fmt: skip
    for mask in range(1, 16):
        add(
            f"stcm-{mask}",
            [*word(0xA1B2, 0xC3D4), "         XC    W_C,W_C", f"         STCM  R2,{mask},W_C"],
            ("W_C",),
            True,
        )
    for mask in (1, 5, 15):
        add(
            f"stcm-at-{mask}",
            [*word(0xA1B2, 0xC3D4), "         XC    W_C,W_C", f"         STCM  R2,{mask},W_C+3"],
            ("W_C",),
            True,
        )
    for v in (0x00, 0x01, 0x7F, 0x80, 0xFF):
        add(f"ic-{v:02x}", [*raw_bytes("W_B", [v]), "         LA    R3,1883", "         IC    R3,W_B"], ("W_B",), True)
    for v in (0, 1, 15, 16, 128, 255):
        add(f"ic-tbl-{v}", ["         LA    R5," + str(v), "         IC    R5,TBL(R5)", DATA, *TABLE], (), True)
    vals = [0, 1, 15, 16, 127, 128, 254, 255]
    for n in (1, 3, 8):
        add(f"tr-{n}", [*raw_bytes("W_B", vals), f"         TR    W_B({n}),TBL", DATA, *TABLE], ("W_B",), True)
    return out


def source(code: list[str]) -> str:
    if DATA in code:
        at = code.index(DATA)
        code, data = code[:at], ["         LTORG", "         DS    0F", *code[at + 1 :]]
    else:
        data = []
    return "\n".join([*PRELUDE, *code, RETURN, *data, *ENDING]) + "\n"


def interpret(code: list[str], name: str = "") -> dict[str, int]:
    """The registers, and the bytes of the case's fields (`W_B[0]`...; a text byte as its ASCII code, see the header)."""
    machine = H.Machine(source(code))
    res = machine.run(b"")
    out = {f"R{n}": res.regs[n] % 2**32 for n in OBSERVED}
    for field in BYTES.get(name, ()):
        sym = machine.syms[field]
        for i in range(sym.length):
            b = res.mem[H.WS + sym.off + i]
            out[f"{field}[{i}]"] = b if name in RAW else ord(bytes([b]).decode(H.EBCDIC))
    return out


def lowered(code: list[str], name: str = "") -> str | None:
    """The COBOL program with its closing EXEC CICS RETURN replaced by a DISPLAY of every register it uses."""
    text = hlasm.lower_text(source(code), "T.asm")
    used = sorted({int(n) for n in re.findall(r"HL-R(\d+) PIC", text)})
    shows = "".join(f'           DISPLAY "R{n}=" HL-R{n}\n' for n in used if n in OBSERVED)
    for field in BYTES.get(name, ()):
        for i in range(H.Machine(source(code)).syms[field].length):
            shows += f'           DISPLAY "{field}[{i}]=" FUNCTION ORD({field.replace("_", "-")}({i + 1}:1))\n'
    text = text.replace(
        "EXEC CICS ABEND ABCODE('ASRA') NODUMP END-EXEC", "STOP RUN"
    )  # the address guard: never taken here
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
        elif m := re.fullmatch(r"(R\d|W_\w+\[\d+\])=([+-]?\d+)", line.strip()):
            seen[cur][m.group(1)] = int(m.group(2)) % 2**32 - (1 if m.group(1)[0] == "W" else 0)  # ORD counts from 1
    by_id = {v: k for k, v in names.items()}
    return {by_id[k]: v for k, v in seen.items()}


def differences() -> list[str]:
    cs = cases()
    progs = {}
    for name, code in cs.items():
        text = lowered(code, name)
        if text is not None:
            progs[name] = text
    got = run_cobol(progs)
    out = []
    for name, code in cs.items():
        want = interpret(code, name)
        have = got.get(name)
        if not have:
            out.append(f"{name}: cobc produced no registers")
            continue
        out += [f"{name}: {k} not displayed by the lowering" for k in want if "[" in k and k not in have]
        for reg, val in have.items():
            if want.get(reg) != val:
                out.append(f"{name}: {reg} interpreter {want[reg]} lowering {val}")
    return out
