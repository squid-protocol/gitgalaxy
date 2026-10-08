"""#4662 (oracle_assumptions.md C11): a zoned item holding non-digits -- spaces, letters, low-values, X'FF' -- read as
a MOVE sender (to a zoned, packed, numeric-edited or binary item), an arithmetic operand (COMPUTE / ADD / SUBTRACT) and
a comparand, and the sign GnuCOBOL 3.1.2 (`-std=ibm -fsign=EBCDIC`, the oracle) writes back over a signed sender's
sign byte even for digit-only data. IBM documents no result for non-digit data in a numeric item, so the det runtime
models the oracle (cobolrt/Zoned.java; each rule's libcob function is named there and in C11).

One program per sender shape (unsigned, SIGN TRAILING, SIGN LEADING, TRAILING / LEADING SEPARATE), each case a byte
string in the sender and each operation a line: the receivers' bytes, the sender's bytes afterwards. The expected
lines (nondigit_zoned_expected.txt) are what cobc prints; the port must print the same under TRUNC(STD) and TRUNC(BIN).
`EQUIVALENCE_E2E=1` (Docker) also compiles the same programs with cobc and checks the file is still the oracle's;
`python tests/cobol_mainframe/test_det_nondigit_zoned.py` rewrites the file from cobc.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_det_nondigit_binary import FLAGS, IMAGE, _det, _java  # noqa: E402

EXPECTED = Path(__file__).with_name("nondigit_zoned_expected.txt")

# kind: (PICTURE clause of the sender, bytes in it)
KINDS = {
    "U": ("PIC 9(4)", 4), "T": ("PIC S9(4)", 4), "L": ("PIC S9(4) SIGN LEADING", 4),
    "TS": ("PIC S9(4) SIGN TRAILING SEPARATE", 5), "LS": ("PIC S9(4) SIGN LEADING SEPARATE", 5),
}  # fmt: skip
# the bytes each sender holds; a byte >= X'80' in a digit position is left to the operations that print numbers
# (the port's DISPLAY writes a character above 0x7F as UTF-8, the oracle as the byte: a different matter)
CASES = {
    "U": [b"    ", b"12A4", b"1 34", b"\0\0\0\0", b"12\xff4", b"1234", b"0012"],
    "T": [b"    ", b"12A4", b"123 ", b"123}", b"1234", b"\0\0\0\0", b"123\xff", b"123!", b"12 4", b"123J", b"123p"],
    "L": [b"    ", b" 123", b"{123", b"1234", b"}123", b"\xff123", b"!123", b"J123"],
    "TS": [b"12A4+", b"12 4-", b"1234 ", b"1234\0", b"1234+", b"1234-", b"    +", b"    -", b"1234x"],
    "LS": [b"+12A4", b"-12 4", b" 1234", b"+1234", b"-1234", b"+    ", b"-    "],
}  # fmt: skip
DATA = [
    "01 DU PIC 9(7).", "01 DUX REDEFINES DU PIC X(7).", "01 DS PIC S9(7).", "01 DSX REDEFINES DS PIC X(7).",
    "01 DLS PIC S9(7) SIGN LEADING SEPARATE.", "01 DLSX REDEFINES DLS PIC X(8).",
    "01 DTS PIC S9(7) SIGN TRAILING SEPARATE.", "01 DTSX REDEFINES DTS PIC X(8).",
    "01 DV PIC 9(5)V99.", "01 DVX REDEFINES DV PIC X(7).",
    "01 PK PIC S9(7) COMP-3.", "01 PKN REDEFINES PK PIC 9(9) COMP-5.",
    "01 UPK PIC 9(6) COMP-3.", "01 UPKN REDEFINES UPK PIC 9(9) COMP-5.",
    "01 BN PIC S9(9) COMP.", "01 BU PIC 9(9) COMP.", "01 EW PIC -9(12).",
    "01 E1 PIC Z(6)9.", "01 E2 PIC -9(6).", "01 E3 PIC 9(4).99.", "01 E4 PIC +9(6).",
]  # fmt: skip
# '@' the sender, '#' the case label; every operation starts from the case's bytes again
OPS = [
    ["MOVE @ TO DU", "DISPLAY '#>DU ' DUX"], ["MOVE @ TO DS", "DISPLAY '#>DS ' DSX"],
    ["MOVE @ TO DLS", "DISPLAY '#>DLS ' DLSX"], ["MOVE @ TO DTS", "DISPLAY '#>DTS ' DTSX"],
    ["MOVE @ TO DV", "DISPLAY '#>DV ' DVX"],
    ["MOVE @ TO PK", "MOVE PKN TO EW", "DISPLAY '#>PK ' EW"],
    ["MOVE @ TO UPK", "MOVE UPKN TO EW", "DISPLAY '#>UPK ' EW"],
    ["MOVE @ TO E1", "DISPLAY '#>E1 [' E1 ']'"], ["MOVE @ TO E2", "DISPLAY '#>E2 [' E2 ']'"],
    ["MOVE @ TO E3", "DISPLAY '#>E3 [' E3 ']'"], ["MOVE @ TO E4", "DISPLAY '#>E4 [' E4 ']'"],
    ["MOVE @ TO BN", "MOVE BN TO EW", "DISPLAY '#>BN ' EW"], ["MOVE @ TO BU", "MOVE BU TO EW", "DISPLAY '#>BU ' EW"],
    ["MOVE 5 TO BN", "COMPUTE BN = @", "MOVE BN TO EW", "DISPLAY '#=' EW"],
    ["MOVE 5 TO BN", "ADD @ TO BN", "MOVE BN TO EW", "DISPLAY '#+BN ' EW"],
    ["MOVE 5 TO DS", "ADD @ TO DS", "DISPLAY '#+DS ' DSX"], ["MOVE 50 TO DS", "SUBTRACT @ FROM DS", "DISPLAY '#-DS ' DSX"],
    ["MOVE 5 TO PK", "ADD @ TO PK", "MOVE PKN TO EW", "DISPLAY '#+PK ' EW"],
    ["MOVE 5 TO DS", "COMPUTE DS = @ + 1", "DISPLAY '#+1 ' DSX"],
    ["IF @ = 0", "DISPLAY '#=0 y'", "ELSE", "DISPLAY '#=0 n'", "END-IF"],
    ["IF @ > 5", "DISPLAY '#>5 y'", "ELSE", "DISPLAY '#>5 n'", "END-IF"],
    ["MOVE 5 TO DU", "IF @ < DU", "DISPLAY '#<DU y'", "ELSE", "DISPLAY '#<DU n'", "END-IF"],
    ["IF @ IS NUMERIC", "DISPLAY '#num y'", "ELSE", "DISPLAY '#num n'", "END-IF"],
    ["IF @ IS POSITIVE", "DISPLAY '#pos y'", "ELSE", "DISPLAY '#pos n'", "END-IF"],
]  # fmt: skip
# the operations that print the sender's bytes as they are (a byte >= X'80' in a digit position stays out of them)
RAW = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}  # the zoned and edited receivers; packed ones as a COMP-5 number


def _program(kind: str) -> str:
    pic, ln = KINDS[kind]
    data = DATA + [f"01 R PIC X({ln}).", f"01 S REDEFINES R {pic}."]
    proc = []
    for n, b in enumerate(CASES[kind], 1):
        label = f"{kind}{n}"
        high = any(c >= 0x80 for c in (b[1:-1] if kind in ("TS", "LS") else b))
        high = high and not (kind in ("T", "TS") and b[-1] >= 0x80 and all(c < 0x80 for c in b[:-1]))
        high = high and not (kind in ("L", "LS") and b[0] >= 0x80 and all(c < 0x80 for c in b[1:]))
        for i, op in enumerate(OPS):
            if high and i in RAW:
                continue
            proc.append(f"MOVE X'{b.hex().upper()}' TO R")
            proc += [x.replace("@", "S").replace("#", label) for x in op]
            if any(c >= 0x80 for c in b):
                proc.append("INSPECT R CONVERTING X'FF' TO '#'")
            proc.append(f"DISPLAY '{label}af ' R")
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."]  # fmt: skip
    lines += [f"       {x}" for x in data] + ["       PROCEDURE DIVISION."] + [f"           {x}" for x in proc]
    return "\n".join(lines + ["           GOBACK.", ""])


def _esc(text: str) -> list[str]:
    """Output lines with every byte outside printable ASCII written as \\xNN (a NUL, X'FF')."""
    return ["".join(c if " " <= c <= "~" else f"\\x{ord(c) % 256:02x}" for c in x) for x in text.split("\n")[:-1]]


def _expected() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = ""
    for line in EXPECTED.read_text().split("\n"):
        if line.startswith("== "):
            key = line[3:]
            out[key] = []
        elif key and line != "== end":
            out[key].append(line)
    return out


def _cobc(kind: str, trunc: str, work: Path) -> str:
    (work / "ndb.cbl").write_text(_program(kind))
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          f"cobc -x -std=ibm -fsign=EBCDIC {FLAGS[trunc]} ndb.cbl -o ndb 2>&1 && ./ndb"],
                         capture_output=True, check=False)  # fmt: skip
    text = run.stdout.decode("latin-1")
    assert run.returncode == 0, text
    return text


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("trunc", ["STD", "BIN"])
@pytest.mark.parametrize("kind", list(KINDS))
def test_nondigit_zoned_is_the_oracles(kind, trunc, tmp_path):
    """Each sender shape x operation: the port prints what cobc printed (nondigit_zoned_expected.txt)."""
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_program(kind), tmp_path, trunc)
    assert run.returncode == 0, run.stderr
    assert _esc(run.stdout) == _expected()[f"{kind} {trunc}"]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker (EQUIVALENCE_E2E=1)")  # fmt: skip
@pytest.mark.parametrize("trunc", ["STD", "BIN"])
@pytest.mark.parametrize("kind", list(KINDS))
def test_the_expected_lines_are_cobcs(kind, trunc, tmp_path):
    assert _esc(_cobc(kind, trunc, tmp_path)) == _expected()[f"{kind} {trunc}"]


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_what_is_not_measured_is_refused_by_name(tmp_path):
    """Arithmetic on 19 digits of which one is a non-digit has no measured libcob path here (C11): refused, never
    guessed."""
    pytest.importorskip("tree_sitter_language_pack")
    proc = ["MOVE '1234567890123456 8 ' TO XL", "COMPUTE BN = L19"]
    data = ["01 XL PIC X(19).", "01 L19 REDEFINES XL PIC 9(19).", "01 BN PIC S9(9) COMP."]
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."] + [f"       {x}" for x in data]  # fmt: skip
    src = "\n".join(
        lines + ["       PROCEDURE DIVISION."] + [f"           {x}" for x in proc] + ["           GOBACK.", ""]
    )
    run = _det(src, tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr and "is not modelled" in run.stderr, run.stderr


if __name__ == "__main__":  # rewrite nondigit_zoned_expected.txt from cobc
    import tempfile

    parts = []
    for k in KINDS:
        for t in ("STD", "BIN"):
            with tempfile.TemporaryDirectory() as d:
                parts += [f"== {k} {t}", *_esc(_cobc(k, t, Path(d))), "== end"]
    EXPECTED.write_text("\n".join(parts) + "\n")
