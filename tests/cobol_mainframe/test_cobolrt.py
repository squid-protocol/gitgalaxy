"""The det-port Java runtime (gitgalaxy/tools/cobol_to_java/det/cobolrt) against GnuCOBOL.

One COBOL program performs every case of the matrix (MOVE across categories, arithmetic stores, compares, class
tests, DISPLAY, STRING / UNSTRING / INSPECT) and dumps each target's bytes as hex through a called DUMPER program;
`cobc -x -std=ibm -fsign=EBCDIC` in the gitgalaxy-gnucobol:3 image, DISPLAY through tests/equivalence/faults/ggdisplay.c as
the equivalence harness runs it. The same cases run through the Java runtime (initial images read from what the COBOL
program dumped before each case), and each case's bytes must be equal. Needs EQUIVALENCE_E2E=1 and Docker.

A case's COBOL text is written by the item names it declares (SND, RCV, ...); the generator prefixes them with the
case id. Where GnuCOBOL surprised us, the case says what it showed.
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq

REPO = Path(__file__).resolve().parents[2]
RT = REPO / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"
JAVA_BIN = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin")
PKG = "ggtest"

pytestmark = pytest.mark.skipif(
    os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"), reason="needs Docker"
)


# ------------------------------------------------------------------------------------------------ item specs


def _expand(pic: str) -> str:
    out = ""
    i = 0
    while i < len(pic):
        c = pic[i]
        if c == "(":
            j = pic.index(")", i)
            out += out[-1] * (int(pic[i + 1 : j]) - 1)
            i = j
        else:
            out += c
        i += 1
    return out


@dataclass(frozen=True)
class Spec:
    kind: str  # X A G N E AE T
    pic: str = ""
    n: int = 0  # X / A / G length, T element count
    usage: str = ""  # N: "", COMP-3, COMP, COMP-5
    sign: str = ""  # N: "", LEADING, "LEADING SEPARATE", "TRAILING SEPARATE"
    jr: bool = False
    bwz: bool = False
    elem: int = 0  # T element length

    def numeric(self) -> tuple[int, int, bool]:
        e = _expand(self.pic)
        signed = e.startswith("S")
        e = e.lstrip("S")
        if "V" in e:
            a, b = e.split("V")
        else:
            a, b = e, ""
        return len(a) + len(b), len(b), signed

    def length(self) -> int:
        if self.kind in ("X", "A", "G"):
            return self.n
        if self.kind == "T":
            return self.n * self.elem
        if self.kind == "N":
            d, _, signed = self.numeric()
            if self.usage == "COMP-3":
                return d // 2 + 1
            if self.usage in ("COMP", "COMP-5"):
                return 2 if d <= 4 else 4 if d <= 9 else 8
            return d + (1 if signed and "SEPARATE" in self.sign else 0)
        e = _expand(self.pic).replace("V", "")
        return len(e)

    def decl(self) -> str:
        if self.kind == "X":
            return f"PIC X({self.n})" + (" JUSTIFIED RIGHT" if self.jr else "")
        if self.kind == "A":
            return f"PIC A({self.n})" + (" JUSTIFIED RIGHT" if self.jr else "")
        if self.kind == "N":
            s = f"PIC {self.pic}"
            if self.usage:
                s += f" {self.usage}"
            if self.sign:
                s += f" SIGN {self.sign}"
            return s
        if self.kind == "E":
            return f"PIC {self.pic}" + (" BLANK WHEN ZERO" if self.bwz else "")
        if self.kind == "AE":
            return f"PIC {self.pic}"
        return ""

    def java(self, st: str) -> str:
        j = lambda b: "true" if b else "false"  # noqa: E731
        if self.kind == "X":
            return f"Field.alphanumeric({st}, 0, {self.n}, {j(self.jr)})"
        if self.kind == "A":
            return f"Field.alphabetic({st}, 0, {self.n}, {j(self.jr)})"
        if self.kind in ("G", "T"):
            return f"Field.group({st}, 0, {self.length()})"
        if self.kind == "N":
            d, sc, signed = self.numeric()
            if self.usage == "COMP-3":
                return f"Field.packed({st}, 0, {d}, {sc}, {j(signed)})"
            if self.usage in ("COMP", "COMP-5"):
                return f"Field.binary({st}, 0, {d}, {sc}, {j(signed)}, {j(self.usage == 'COMP-5')})"
            return (
                f"Field.zoned({st}, 0, {d}, {sc}, {j(signed)}, {j(self.sign.startswith('LEADING'))}, "
                f"{j('SEPARATE' in self.sign)})"
            )
        if self.kind == "E":
            return f'Field.numericEdited({st}, 0, {self.length()}, "{self.pic}", {j(self.bwz)})'
        return f'Field.alphanumericEdited({st}, 0, {self.length()}, "{self.pic}")'


def X(n, jr=False):
    return Spec("X", n=n, jr=jr)


def A(n, jr=False):
    return Spec("A", n=n, jr=jr)


def G(n):
    return Spec("G", n=n)


def T(count, elem):
    return Spec("T", n=count, elem=elem)


def N(pic, usage="", sign=""):
    return Spec("N", pic=pic, usage=usage, sign=sign)


def E(pic, bwz=False):
    return Spec("E", pic=pic, bwz=bwz)


def AE(pic):
    return Spec("AE", pic=pic)


Init = Union[None, str, bytes]  # str: a COBOL VALUE literal; bytes: the exact image (REDEFINES of a PIC X)


def txt(s: str) -> bytes:
    return s.encode("latin-1")


@dataclass
class Case:
    cid: str
    items: list  # (name, Spec, Init)
    cob: str
    jav: str
    out: tuple = ("RCV",)
    res: bool = False
    disp: tuple = ()
    xfail: Optional[str] = None
    note: str = ""
    names: list = field(default_factory=list)


CASES: list[Case] = []
_COUNT: dict[str, int] = {}


def add(prefix, items, cob, jav, out=("RCV",), res=False, disp=(), xfail=None, note=""):
    _COUNT[prefix] = _COUNT.get(prefix, 0) + 1
    cid = f"{prefix}{_COUNT[prefix]:02d}"
    items = [(n, s, i) for n, s, i in items]
    CASES.append(Case(cid, items, cob, jav, tuple(out), res, tuple(disp), xfail, note))


def mv(snd, rcv, note="", xfail=None):
    add("MV", [("SND", *snd), ("RCV", *rcv)], "MOVE SND TO RCV", "Cobol.move(SND, RCV, CS);", xfail=xfail, note=note)


def mvlit(lit_cob, lit_java, rcv, note="", xfail=None):
    add("ML", [("RCV", *rcv)], f"MOVE {lit_cob} TO RCV", f"Cobol.move({lit_java}, RCV, CS);", xfail=xfail, note=note)


def mvfig(fig, rcv, note="", xfail=None):
    cob = {
        "SPACES": "SPACES",
        "ZEROS": "ZEROS",
        "LOW_VALUES": "LOW-VALUES",
        "HIGH_VALUES": "HIGH-VALUES",
        "QUOTES": "QUOTES",
    }[fig]
    add(
        "MF",
        [("RCV", *rcv)],
        f"MOVE {cob} TO RCV",
        f"Cobol.moveFigurative(Figurative.{fig}, RCV, CS);",
        xfail=xfail,
        note=note,
    )


def mvall(lit, rcv, note="", xfail=None):
    add("MA", [("RCV", *rcv)], f'MOVE ALL "{lit}" TO RCV', f'Cobol.moveAll("{lit}", RCV, CS);', xfail=xfail, note=note)


BD = lambda s: f'new BigDecimal("{s}")'  # noqa: E731

# ---------------------------------------------------------------------------------------------- MOVE matrix

# alphanumeric -> alphanumeric
mv((X(5), '"ABC"'), (X(8), None), "left-justified, space padded")
mv((X(8), '"ABCDEFGH"'), (X(3), None), "truncated on the right")
mv((X(3), '"ABC"'), (X(5, jr=True), None), "JUSTIFIED RIGHT: padded on the left")
mv((X(8), '"ABCDEFGH"'), (X(3, jr=True), None), "JUSTIFIED RIGHT: the low-order end kept")
mv((X(4), '"ABCD"'), (A(6), None), "to alphabetic")
mv((G(6), txt("AB") + b"\x00\xffCD"), (X(8), None), "group to alphanumeric: no conversion")
# numeric DISPLAY to alphanumeric: the digit bytes as they are (invalid data too), the sign de-punched
mv((N("9(11)"), txt("ABC        ")), (X(11), None), "invalid unsigned zoned to alphanumeric: bytes kept")
mv((N("S9(11)"), txt("ABC0000000C")), (X(11), None), "invalid signed zoned to alphanumeric: bytes, sign de-punched")
mv((N("S9(5)"), txt("0001K")), (X(7), None), "signed zoned to alphanumeric: sign de-punched")
mv((N("9(3)V99"), txt("12345")), (X(7), None), "scaled zoned to alphanumeric: digits, no point")
mv((N("S9(5)", sign="LEADING SEPARATE"), txt("+00012")), (X(7), None), "separate sign dropped")
mv((X(4), '"WXYZ"'), (G(6), txt("123456")), "alphanumeric to group: space padded")
mv((G(6), txt("ABCDEF")), (G(4), txt("1234")), "group to group truncates")
mv(
    (G(3), txt("ABC")),
    (
        G(
            6,
        ),
        txt("123456"),
    ),
    "group to group pads",
)
mvlit('"HELLO"', '"HELLO"', (X(3), None), "literal truncated")
mvlit('"HELLO"', '"HELLO"', (X(7), None), "literal padded")
mvlit('"HELLO"', '"HELLO"', (X(7, jr=True), None), "literal to JUSTIFIED RIGHT")
add(
    "MR",
    [("SND", X(6), '"ABCDEF"'), ("RCV", X(4), None)],
    "MOVE SND(2:3) TO RCV",
    "Cobol.move(SND.ref(2, 3), RCV, CS);",
)
add(
    "MR",
    [("SND", X(6), '"ABCDEF"'), ("RCV", X(6), '"123456"')],
    "MOVE SND(3:) TO RCV(2:)",
    "Cobol.move(SND.ref(3, null), RCV.ref(2, null), CS);",
)
add("MR", [("RCV", X(6), '"ABCDEF"')], 'MOVE "ZZ" TO RCV(3:2)', 'Cobol.move("ZZ", RCV.ref(3, 2), CS);')
add(
    "MR",
    [("SND", T(3, 2), txt("ABCDEF")), ("RCV", X(4), None)],
    "MOVE SND-EL (2) TO RCV",
    "Cobol.move(Field.alphanumeric(SND_s, 0, 2, false).at(2, 2), RCV, CS);",
)

# numeric literal
mvlit("123.45", BD("123.45"), (N("S9(3)V9"), None), "literal truncated to one decimal")
mvlit("-7", BD("-7"), (N("9(3)"), None), "negative literal to unsigned: magnitude")
mvlit("12345.678", BD("12345.678"), (N("S9(3)V99", "COMP-3"), None), "high and low digits dropped")
mvlit("5", BD("5"), (X(3), None), "numeric literal to alphanumeric")
mvlit("23", BD("23"), (G(2), None), "numeric literal to a group: its digits, no sign")
mvlit("-12.5", BD("-12.5"), (E("ZZZ9.99-"), None), "literal to edited")

# numeric -> numeric
N3 = N("9(3)")
mv((N3, "123"), (N("9(5)"), None), "pad high-order zeros")
mv((N3, "123"), (N("9(2)"), None), "high-order digit lost")
mv((N("S9(3)"), "-12"), (N3, None), "unsigned receiver: absolute value")
mv((N("S9(3)"), "-12"), (N("S9(5)"), None), "negative overpunch on the last digit")
mv((N("S9(3)"), "12"), (N("S9(3)"), None), "positive overpunch")
mv((N("S9(3)V99"), "123.45"), (N("9(2)V9"), None), "both ends truncated")
mv((N("S9(3)V99"), "123.45"), (N("9(5)V9(3)"), None), "padded both ends")
mv((N("S9(3)V99"), "123.45"), (N("S9(3)"), None), "decimals dropped, not rounded")
mv((N("S9(3)V99"), "123.45"), (N("9"), None), "one digit kept")
mv((N("S9(3)V99"), "-1.5"), (N("S9(2)V9"), None), "negative scaled")
mv((N("S9(3)V99"), "-0.05"), (N("S9(3)"), None), "a negative that truncates to zero")
mv((N("9(3)V9"), "5.5"), (N("S9(3)V99"), None), "to a wider scale")
mv((N("S9(5)V99", "COMP-3"), "-123.45"), (N("S9(3)"), None), "packed to zoned")
mv((N3, "123"), (N("S9(3)", "COMP-3"), None), "zoned to packed")
mv((N("S9(3)"), "-12"), (N("9(3)", "COMP-3"), None), "negative to unsigned packed: sign F")
mv((N("S9(4)", "COMP"), "1234"), (N3, None), "binary to zoned")
mv(
    (N("S9(9)", "COMP"), "99999"),
    (N("S9(4)", "COMP"), None),
    "GnuCOBOL -std=ibm: binary keeps its 2 bytes, not the PICTURE digits (99999 wraps to 869F)",
)
mv((N("9(5)"), "12345"), (N("9(4)", "COMP"), None), "zoned to binary: truncated to 4 digits")
mv((N("S9(4)", "COMP"), "-300"), (N("S9(4)", "COMP-3"), None), "binary to packed")
mv((N("S9(9)", "COMP"), "-123456789"), (N("S9(5)", "COMP-3"), None), "wide binary to narrow packed")
mv((N("S9(18)", "COMP"), "123456789012345678"), (N("S9(18)"), None), "18-digit binary")
mv((N("9(10)", "COMP"), "4000000000"), (N("S9(10)"), None), "10-digit binary (8 bytes)")
mv((N("S9(4)", "COMP-5"), "1234"), (N("S9(4)"), None), "COMP-5 to zoned")
mv((N("9(5)"), "99999"), (N("S9(4)", "COMP-5"), None), "COMP-5 receiver, no PICTURE truncation?")
mv((N("S9(3)"), "-12"), (N("S9(3)", sign="LEADING SEPARATE"), None), "to SIGN LEADING SEPARATE")
mv((N("S9(3)V9", sign="TRAILING SEPARATE"), "12.5"), (N("S9(3)V9"), None), "from SIGN TRAILING SEPARATE")
mv((N("S9(3)", sign="LEADING"), "-12"), (N("S9(3)"), None), "SIGN LEADING embedded to trailing")
mv((N("S9(3)"), "-12"), (N("S9(3)", sign="LEADING"), None), "trailing to SIGN LEADING embedded")
mv((N("S9(3)"), "-12"), (N("9(3)", sign=""), None), "again unsigned")

mv((N("S9(3)"), "-12"), (N("9(4)", "COMP"), None), "negative into an unsigned binary item")
mv((N("S9(3)"), "-12"), (N("S9(4)", "COMP"), None), "negative into a signed binary item")
mv((N("S9(7)"), "-1234567"), (N("S9(4)", "COMP"), None), "binary wraps at 2 bytes, not at 4 digits")
mv((N("9(4)", "COMP-3"), "1234"), (N("9(6)"), None), "even-digit packed (3 bytes), unsigned")
mv((N("S9(4)"), "-1234"), (N("S9(4)", "COMP-3"), None), "to even-digit packed (leading pad nibble)")
mv((N("S9(3)", sign="TRAILING SEPARATE"), "-12"), (N("S9(3)", sign="LEADING SEPARATE"), None), "separate to separate")
mv((N("S9(5)V99", "COMP-3"), "-123.45"), (N("S9(5)V99", "COMP-5"), None), "packed to COMP-5 (little-endian)")
mv((N("S9(4)", "COMP-5"), "-300"), (N("S9(9)", "COMP"), None), "COMP-5 to COMP")

# numeric -> alphanumeric
mv((N3, "12"), (X(5), None), "digits left-justified")
mv((N3, "123"), (X(2), None), "digits truncated")
mv((N("S9(3)"), "-12"), (X(3), None), "sign dropped")
mv((N("S9(3)V99"), "123.45"), (X(6), None), "scaled sender: its digits")
mv((N("S9(4)", "COMP"), "-7"), (X(6), None), "binary sender")
mv((N("S9(5)V99", "COMP-3"), "12.5"), (X(8), None), "packed sender")
mv((N3, "45"), (X(5, jr=True), None), "to JUSTIFIED RIGHT")
mv((N("S9(3)", sign="LEADING SEPARATE"), "-12"), (X(4), None), "separate sign dropped")

# alphanumeric -> numeric
mv((X(3), '"123"'), (N("9(5)"), None), "digits")
mv((X(5), '"12   "'), (N("9(3)"), None), "trailing spaces")
mv((X(4), '"0045"'), (N("9(2)"), None), "high-order truncated")
mv((X(2), '" 5"'), (N("9(3)"), None), "leading space")
mv((X(3), '"-12"'), (N("S9(3)"), None), "leading sign character")
mv((X(3), '"1.5"'), (N("9(2)V9"), None), "decimal point in the source")
mv((X(6), '"123456"'), (N("9(3)"), None), "more digits than the receiver")
mv((X(3), '"ABC"'), (N("9(3)"), None), "non-digit source")
mv((X(3), '"123"'), (N("S9(3)", "COMP-3"), None), "to packed")
mv((X(3), '"123"'), (N("S9(3)", "COMP"), None), "to binary")
mv((G(3), txt("123")), (N("9(3)"), None), "group to numeric")

# numeric -> numeric edited
for pic, vals in [
    ("ZZZ,ZZ9.99-", ["1234.5", "-1234.5", "0", "0.5", "-0.05"]),
    ("+99999999.99", ["1234.5", "-5"]),
    ("$$$,$$9.99", ["1234.5", "0.05", "123456.78"]),
    ("***,**9.99", ["12.5"]),
    ("ZZ9.99CR", ["-3.5", "3.5"]),
    ("Z9.9", ["12.37"]),
    ("9(3).99", ["5.5"]),
]:
    for v in vals:
        mv((N("S9(7)V99"), v), (E(pic), None), f"{pic} <- {v}")
mv((N("S9(3)"), "0"), (E("ZZ9", bwz=True), None), "BLANK WHEN ZERO")
mv((N("S9(5)V99", "COMP-3"), "1234.5"), (E("ZZ,ZZ9.99"), None), "packed sender to edited")
mv((N("S9(4)", "COMP"), "-1234"), (E("-ZZZ9"), None), "binary sender, floating sign")

# edited -> numeric (de-editing) and edited -> edited
mv((E("ZZZ,ZZ9.99-"), txt("  1,234.50-")), (N("S9(5)V99"), None), "de-edit")
mv((E("ZZZ,ZZ9.99-"), txt("  1,234.50-")), (N("9(3)V9"), None), "de-edit to unsigned, truncating")
mv((E("+99999999.99"), txt("+00001234.50")), (N("S9(5)V99", "COMP-3"), None), "leading sign de-edit")
mv((E("ZZ9.99CR"), txt("  3.50CR")), (N("S9(3)V99"), None), "CR de-edit")
mv((E("ZZZ,ZZ9.99-"), txt("  1,234.50-")), (E("$$$,$$9.99"), None), "edited to edited")
mv((E("ZZ9.99"), txt(" 12.30")), (X(8), None), "edited to alphanumeric: its bytes")

# figurative constants. cobc refuses MOVE SPACES to a numeric or edited-numeric item at compile time ("MOVE of
# figurative constant SPACE to numeric item used"), so those cases cannot exist in a program that compiles.
for fig in ("SPACES", "ZEROS", "LOW_VALUES", "HIGH_VALUES", "QUOTES"):
    mvfig(fig, (X(4), None), f"{fig} to alphanumeric")
mvfig("ZEROS", (N("9(3)"), "123"), "ZEROS to zoned")
mvfig("ZEROS", (N("S9(3)", "COMP-3"), "123"), "ZEROS to packed")
mvfig("ZEROS", (N("S9(4)", "COMP"), "123"), "ZEROS to binary")
mvfig("ZEROS", (E("ZZ9.99"), None), "ZEROS to edited")
mvfig("LOW_VALUES", (N("9(3)"), "123"), "LOW-VALUES to zoned")
mvfig("HIGH_VALUES", (N("9(3)"), "123"), "HIGH-VALUES to zoned")
mvfig("ZEROS", (G(4), txt("ABCD")), "ZEROS to group")
mvfig("HIGH_VALUES", (G(4), txt("ABCD")), "HIGH-VALUES to group")

# MOVE ALL
mvall("AB", (X(5), None), "ALL to alphanumeric")
mvall("*", (X(3), None), "ALL of one character")
mvall("12", (N("9(5)"), None), "ALL to zoned")
mvall("0", (N("S9(3)"), None), "ALL zero to signed zoned")
mvall("AB", (G(5), txt("12345")), "ALL to group")

# alphanumeric edited, group <- numeric
mv((X(6), '"ABCDEF"'), (AE("XX/XX/XX"), None), "alphanumeric edited: / inserted")
mv((X(6), '"ABCDEF"'), (AE("XXBXXB00"), None), "alphanumeric edited: B and 0")
mv((N("S9(3)"), "-12"), (G(6), txt("123456")), "numeric to group: the bytes")
mv((N("S9(3)", "COMP-3"), "-12"), (G(6), txt("123456")), "packed to group: the bytes")

# ------------------------------------------------------------------------------------- arithmetic store cases


def arith(items, cob, jav, note="", xfail=None, res=False):
    add("AR", items, cob, jav, out=("RCV",) + (("RES",) if res else ()), res=res, xfail=xfail, note=note)


n = lambda v: f"Cobol.num({v}, CS)"  # noqa: E731
S = "Cobol.store(RCV, {}, {}, CS);"
SC = 'if (Cobol.storeChecked(RCV, {}, {}, CS)) Cobol.move("E", RES, CS);'
ERR = 'ON SIZE ERROR MOVE "E" TO RES'

arith([("AA", N("9(2)V99"), "12.34"), ("BB", N("9(2)V99"), "5.67"), ("RCV", N("9(3)V99"), None)],
      "COMPUTE RCV = AA * BB", S.format(f"{n('AA')}.multiply({n('BB')})", "false"), "truncated, not rounded")  # fmt: skip
arith([("AA", N("9(2)V99"), "12.34"), ("BB", N("9(2)V99"), "5.67"), ("RCV", N("9(3)V99"), None)],
      "COMPUTE RCV ROUNDED = AA * BB", S.format(f"{n('AA')}.multiply({n('BB')})", "true"))  # fmt: skip
arith([("AA", N("S9(3)V9"), "-2.5"), ("RCV", N("S9"), None)],
      "COMPUTE RCV ROUNDED = AA", S.format(n("AA"), "true"), "half away from zero for a negative")  # fmt: skip
arith([("AA", N("S9(3)V9"), "-2.5"), ("RCV", N("S9"), None)],
      "COMPUTE RCV = AA", S.format(n("AA"), "false"))  # fmt: skip
arith([("AA", N("S9(3)V9"), "2.5"), ("RCV", N("S9"), None)],
      "COMPUTE RCV ROUNDED = AA", S.format(n("AA"), "true"))  # fmt: skip
arith([("AA", N("9(3)"), "999"), ("RCV", N("9(3)"), None)],
      "COMPUTE RCV = AA + 1", S.format(f"{n('AA')}.add(BigDecimal.ONE)", "false"), "no SIZE ERROR: high digit lost")  # fmt: skip
arith([("AA", N("9(3)"), "999"), ("RCV", N("9(3)"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA + 1 {ERR} END-COMPUTE", SC.format(f"{n('AA')}.add(BigDecimal.ONE)", "false"), "SIZE ERROR: unchanged", res=True)  # fmt: skip
arith([("AA", N("S9(3)"), "-999"), ("RCV", N("S9(3)"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA - 5 {ERR} END-COMPUTE", SC.format(f"{n('AA')}.subtract(new BigDecimal(5))", "false"), "negative size error", res=True)  # fmt: skip
arith([("AA", N("9(3)"), "123"), ("RCV", N("S9(4)", "COMP"), None)],
      "COMPUTE RCV = AA * 100", S.format(f"{n('AA')}.multiply(new BigDecimal(100))", "false"), "binary: truncated to the PICTURE digits")  # fmt: skip
arith([("AA", N("9(3)"), "123"), ("RCV", N("S9(4)", "COMP"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA * 100 {ERR} END-COMPUTE", SC.format(f"{n('AA')}.multiply(new BigDecimal(100))", "false"), res=True)  # fmt: skip
arith([("AA", N("S9(4)"), "-1234"), ("RCV", N("S9(5)V99", "COMP-3"), None)],
      "COMPUTE RCV = AA * 1.5", S.format(f"{n('AA')}.multiply({BD('1.5')})", "false"), "packed receiver")  # fmt: skip
arith([("AA", N("9(3)"), "3"), ("BB", N("9(3)"), "5"), ("RCV", N("9(3)"), None)],
      "COMPUTE RCV = AA - BB", S.format(f"{n('AA')}.subtract({n('BB')})", "false"), "negative result into an unsigned item")  # fmt: skip
arith([("AA", N("9(2)"), "10"), ("RCV", N("9(3)"), "995")],
      "ADD AA TO RCV", S.format(f"{n('RCV')}.add({n('AA')})", "false"), "ADD overflows an unsigned zoned item")  # fmt: skip
arith([("AA", N("9(2)"), "10"), ("RCV", N("9(3)"), "995"), ("RES", X(8), None)],
      f"ADD AA TO RCV {ERR} END-ADD", SC.format(f"{n('RCV')}.add({n('AA')})", "false"), res=True)  # fmt: skip
arith([("AA", N("9(2)"), "10"), ("RCV", N("S9(3)"), "5")],
      "SUBTRACT AA FROM RCV", S.format(f"{n('RCV')}.subtract({n('AA')})", "false"))  # fmt: skip
arith([("AA", N("9(2)V9"), "1.5"), ("RCV", N("9(3)V9"), "2.5")],
      "MULTIPLY AA BY RCV ROUNDED", S.format(f"{n('RCV')}.multiply({n('AA')})", "true"), "3.75 to one decimal")  # fmt: skip
arith([("AA", N("9(3)"), "10"), ("BB", N("9(3)"), "3"), ("RCV", N("9(3)V99"), None)],
      "DIVIDE AA BY BB GIVING RCV ROUNDED", S.format(f"{n('AA')}.divide({n('BB')}, 40, RoundingMode.HALF_UP)", "true"))  # fmt: skip
arith([("AA", N("9(3)"), "2"), ("BB", N("9(3)"), "3"), ("RCV", N("9V99"), None)],
      "DIVIDE AA BY BB GIVING RCV", S.format(f"{n('AA')}.divide({n('BB')}, 40, RoundingMode.HALF_UP)", "false"), "truncated 0.66")  # fmt: skip
arith([("AA", N("99V99"), "99.95"), ("RCV", N("99V9"), "1.1"), ("RES", X(8), None)],
      f"COMPUTE RCV ROUNDED = AA {ERR} END-COMPUTE", SC.format(n("AA"), "true"), "rounding carries into a size error", res=True)  # fmt: skip
arith([("AA", N("9(4)"), "9999"), ("RCV", N("S9(4)", "COMP-5"), None)],
      "COMPUTE RCV = AA + 1", S.format(f"{n('AA')}.add(BigDecimal.ONE)", "false"), "COMP-5: no PICTURE truncation")  # fmt: skip
arith([("AA", N("9(5)"), "70000"), ("RCV", N("S9(4)", "COMP-5"), None)],
      "COMPUTE RCV = AA", S.format(n("AA"), "false"), "COMP-5 beyond two bytes")  # fmt: skip
arith([("AA", N("S9(3)V99"), "12.34"), ("BB", N("9(3)"), "2"), ("RCV", E("ZZ9.99"), None)],
      "COMPUTE RCV = AA * BB", S.format(f"{n('AA')}.multiply({n('BB')})", "false"), "edited receiver")  # fmt: skip
arith([("AA", N("S9(5)V99", "COMP-3"), "-1234.56"), ("RCV", N("S9(5)V99", "COMP-3"), "100")],
      "ADD AA TO RCV", S.format(f"{n('RCV')}.add({n('AA')})", "false"), "packed ADD")  # fmt: skip
arith([("AA", N("S9(4)", "COMP"), "500"), ("RCV", N("S9(4)", "COMP"), "-700")],
      "ADD AA TO RCV", S.format(f"{n('RCV')}.add({n('AA')})", "false"), "binary ADD")  # fmt: skip
arith([("AA", N("9(4)"), "7"), ("RCV", N("9(3)"), "0")],
      "COMPUTE RCV = (AA + 3) * 2 - 1", S.format(f"{n('AA')}.add(new BigDecimal(3)).multiply(new BigDecimal(2)).subtract(BigDecimal.ONE)", "false"))  # fmt: skip

arith([("AA", N("9(5)"), "40000"), ("RCV", N("S9(4)", "COMP"), "7")],
      "COMPUTE RCV = AA", S.format(n("AA"), "false"), "binary S9(4): 40000 wraps in two bytes")  # fmt: skip
arith([("AA", N("9(5)"), "40000"), ("RCV", N("S9(4)", "COMP"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA {ERR} END-COMPUTE", SC.format(n("AA"), "false"), "SIZE ERROR for a binary item: past the two bytes", res=True)  # fmt: skip
arith([("AA", N("9(5)"), "70000"), ("RCV", N("9(4)", "COMP"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA {ERR} END-COMPUTE", SC.format(n("AA"), "false"), "unsigned binary: size error past 65535", res=True)  # fmt: skip
arith([("AA", N("9(5)"), "60000"), ("RCV", N("9(4)", "COMP"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA {ERR} END-COMPUTE", SC.format(n("AA"), "false"), "unsigned binary: 60000 fits two bytes", res=True)  # fmt: skip
arith([("AA", N("9(3)"), "5"), ("RCV", N("9(4)", "COMP"), "7")],
      "COMPUTE RCV = 0 - AA", S.format(f"BigDecimal.ZERO.subtract({n('AA')})", "false"), "negative result into an unsigned binary item")  # fmt: skip
arith([("AA", N("9(10)"), "5000000000"), ("RCV", N("S9(9)", "COMP"), "7"), ("RES", X(8), None)],
      f"COMPUTE RCV = AA {ERR} END-COMPUTE", SC.format(n("AA"), "false"), "four-byte binary overflow", res=True)  # fmt: skip
arith([("AA", N("S9(5)V99", "COMP-3"), "-1.5"), ("RCV", N("S9(3)"), "7")],
      "COMPUTE RCV = AA * 0.001", S.format(f"{n('AA')}.multiply({BD('0.001')})", "false"), "a negative that truncates to zero (negative zero?)")  # fmt: skip

# ------------------------------------------------------------------------------------------------- compare


def cmp_case(a, b, cob_b=None, jav_b=None, note="", xfail=None, a_b="SND", fig=None):
    items = [("SND", *a)]
    if b is not None:
        items.append(("RCV", *b))
    other = "RCV" if cob_b is None else cob_b
    jother = "RCV" if jav_b is None else jav_b
    cob = (
        f'IF SND < {other} MOVE "LT" TO RES ELSE IF SND = {other} MOVE "EQ" TO RES ELSE MOVE "GT" TO RES END-IF END-IF'
    )
    jav = f'int c = {jother}; Cobol.move(c < 0 ? "LT" : c == 0 ? "EQ" : "GT", RES, CS);'
    items.append(("RES", X(8), None))
    add("CP", items, cob, jav, out=("RES",), res=False, xfail=xfail, note=note)


def cmp_fields(a, b, note="", xfail=None):
    cmp_case(a, b, None, "Cobol.compare(SND, RCV, CS)", note, xfail)


def cmp_lit(a, lit_cob, lit_java, note="", xfail=None):
    cmp_case(a, None, lit_cob, f"Cobol.compare(SND, {lit_java}, CS)", note, xfail)


def cmp_fig(a, fig, note="", xfail=None):
    cob = {
        "SPACES": "SPACES",
        "ZEROS": "ZEROS",
        "LOW_VALUES": "LOW-VALUES",
        "HIGH_VALUES": "HIGH-VALUES",
        "QUOTES": "QUOTES",
    }[fig]
    cmp_case(a, None, cob, f"Cobol.compareFigurative(SND, Figurative.{fig}, CS)", note, xfail)


cmp_fields((N("9(3)"), "123"), (N("9(5)"), "123"), "numeric by value, different sizes")
cmp_fields((N("S9(3)"), "-5"), (N("S9(3)"), "3"), "negative < positive")
cmp_fields((N("S9(3)V99"), "1.5"), (N("9(3)V9"), "1.5"), "scales aligned")
cmp_fields((N("S9(5)V99", "COMP-3"), "-12.34"), (N("S9(4)", "COMP"), "-12"), "packed vs binary")
cmp_fields((N("S9(3)"), "-12"), (N("9(3)"), "12"), "signed vs unsigned")
cmp_fields((X(3), '"AB"'), (X(5), '"AB"'), "padded with spaces: equal")
cmp_fields((X(3), '"ABC"'), (X(5), '"ABC1"'), "shorter padded with a space, 1 > space")
cmp_fields((X(3), '"abc"'), (X(3), '"ABC"'), "ASCII: lower after upper")
cmp_fields((G(3), b"\xff\xfe\x00"), (G(3), txt("ABC")), "bytes above 0x7F compare unsigned")
cmp_fields((G(4), txt("AB") + b"\x00\x00"), (G(2), txt("AB")), "NUL is below space")
cmp_fields((N("9(3)"), "123"), (X(3), '"123"'), "zoned vs alphanumeric: bytes")
cmp_lit((N("S9(3)V99"), "12.5"), "12.50", BD("12.50"), "numeric literal")
cmp_lit((N("9(3)"), "5"), "10", BD("10"), "numeric literal, greater")
cmp_lit((X(5), '"HELLO"'), '"HELLO"', '"HELLO"', "alphanumeric literal")
cmp_lit((X(5), '"HELLO"'), '"HELL"', '"HELL"', "shorter literal padded")
cmp_lit((X(5), '"HELLO"'), '"HELLP "', '"HELLP "', "longer literal")
cmp_fig((X(3), '"   "'), "SPACES", "all spaces")
cmp_fig((X(3), '"ab "'), "SPACES", "not spaces")
cmp_fig((N("9(3)"), "0"), "ZEROS", "numeric zero")
cmp_fig((X(3), '"000"'), "ZEROS", "alphanumeric zeros")
cmp_fig((N("S9(3)", "COMP-3"), "-5"), "ZEROS", "negative packed vs ZEROS")
cmp_fig((G(3), b"\x00\x00\x00"), "LOW_VALUES", "LOW-VALUES")
cmp_fig((G(3), b"\xff\xff\xff"), "HIGH_VALUES", "HIGH-VALUES")
cmp_fig((X(3), '"ZZZ"'), "HIGH_VALUES", "letters below HIGH-VALUES")
cmp_fig((N("9(3)"), "123"), "SPACES", "zoned digits vs SPACES")

cmp_lit((N("9(3)"), "123"), '"123"', '"123"', "numeric item vs alphanumeric literal")
cmp_lit((X(3), '"123"'), "123", BD("123"), "alphanumeric item vs numeric literal")
cmp_lit((X(3), '"  5"'), "5", BD("5"), "alphanumeric with spaces vs numeric literal")
cmp_fields((N("S9(3)V99", "COMP-3"), "0"), (N("S9(3)"), "0"), "zero equals zero")
cmp_fields((N("9(3)"), "100"), (N("9(3)"), "99"), "numeric, not text, order")
cmp_fields((X(3), '"100"'), (X(2), '"99"'), "text order")

# ----------------------------------------------------------------------------------------------- class tests


def cls(spec_init, kind, expect_note="", xfail=None):
    test = {
        "NUMERIC": ("IS NUMERIC", "Cobol.isNumeric(SND, CS)"),
        "ALPHABETIC": ("IS ALPHABETIC", "Cobol.isAlphabetic(SND, CS)"),
        "UPPER": ("IS ALPHABETIC-UPPER", "Cobol.isAlphabeticUpper(SND, CS)"),
        "LOWER": ("IS ALPHABETIC-LOWER", "Cobol.isAlphabeticLower(SND, CS)"),
    }[kind]
    cob = f'IF SND {test[0]} MOVE "YES" TO RES ELSE MOVE "NO" TO RES END-IF'
    jav = f'Cobol.move({test[1]} ? "YES" : "NO", RES, CS);'
    add("CL", [("SND", *spec_init), ("RES", X(8), None)], cob, jav, out=("RES",), xfail=xfail, note=expect_note)


cls((X(3), '"123"'), "NUMERIC", "digits")
cls((X(3), '"12 "'), "NUMERIC", "a space")
cls((X(3), '"1A3"'), "NUMERIC", "a letter")
cls((N("9(3)"), txt("12K")), "NUMERIC", "unsigned zoned with an overpunch")
cls((N("S9(3)"), txt("12K")), "NUMERIC", "signed zoned, negative overpunch")
cls((N("S9(3)"), txt("12B")), "NUMERIC", "signed zoned, positive overpunch")
cls((N("S9(3)"), txt("12Z")), "NUMERIC", "signed zoned, no such overpunch")
cls((N("S9(3)"), txt("12}")), "NUMERIC", "signed zoned, -0")
cls((N("S9(3)"), txt("12 ")), "NUMERIC", "signed zoned, space")
cls((N("S9(3)"), txt("1K3")), "NUMERIC", "overpunch in the middle")
cls((N("S9(3)", sign="LEADING SEPARATE"), txt("-12")), "NUMERIC", "separate sign")
cls((N("S9(3)", sign="LEADING SEPARATE"), txt(" 12")), "NUMERIC", "no sign character")
cls((N("S9(3)", sign="TRAILING SEPARATE"), txt("12+")), "NUMERIC", "trailing separate sign")
cls((N("S9(3)", "COMP-3"), bytes.fromhex("123C")), "NUMERIC", "packed +")
cls((N("S9(3)", "COMP-3"), bytes.fromhex("123D")), "NUMERIC", "packed -")
cls((N("S9(3)", "COMP-3"), bytes.fromhex("123F")), "NUMERIC", "packed unsigned sign nibble in a signed item")
cls((N("S9(3)", "COMP-3"), bytes.fromhex("12AC")), "NUMERIC", "packed bad digit")
cls((N("S9(3)", "COMP-3"), bytes.fromhex("1230")), "NUMERIC", "packed bad sign nibble")
cls((N("S9(3)", "COMP-3"), bytes.fromhex("1237")), "NUMERIC", "packed sign nibble 7")
cls((N("9(3)", "COMP-3"), bytes.fromhex("123C")), "NUMERIC", "unsigned packed with sign C")
cls((N("9(3)", "COMP-3"), bytes.fromhex("123F")), "NUMERIC", "unsigned packed with sign F")
cls((N("S9(4)", "COMP"), bytes.fromhex("7FFF")), "NUMERIC", "binary beyond the PICTURE digits")
cls((N("S9(4)", "COMP"), bytes.fromhex("0064")), "NUMERIC", "binary within")
cls((X(5), '"ABC  "'), "ALPHABETIC", "letters and spaces")
cls((X(3), '"AB1"'), "ALPHABETIC", "a digit")
cls((X(3), '"abc"'), "ALPHABETIC", "lower case letters")
cls((X(3), '"AbC"'), "UPPER", "mixed")
cls((X(3), '"ABC"'), "UPPER", "upper")
cls((X(3), '"A C"'), "UPPER", "upper with a space")
cls((X(3), '"abc"'), "LOWER", "lower")
cls((X(3), '"a c"'), "LOWER", "lower with a space")
cls((X(3), '"aBc"'), "LOWER", "mixed")
cls((X(3), '"   "'), "ALPHABETIC", "all spaces")

# -------------------------------------------------------------------------------------------- displayText


def disp(spec_init, note="", xfail=None):
    add(
        "DP",
        [("SND", *spec_init)],
        'DISPLAY "D|{CID}|" SND',
        'out.println("D|{CID}|" + Cobol.displayText(SND, CS));',
        out=("SND",),
        disp=("SND",),
        xfail=xfail,
        note=note,
    )


disp((N("9(3)"), "12"), "unsigned zoned")
disp((N("S9(3)"), "-12"), "signed negative: overpunch")
disp((N("S9(3)"), "12"), "signed positive: overpunch")
disp((N("S9(3)V99"), "-1.5"), "scaled signed: no decimal point")
disp((N("9(3)V99"), "1.5"), "scaled unsigned zoned")
disp((N("S9(3)", sign="LEADING SEPARATE"), "-12"), "leading separate")
disp((N("S9(3)", sign="TRAILING SEPARATE"), "-12"), "trailing separate")
disp((N("S9(3)V9", sign="LEADING SEPARATE"), "12.5"), "leading separate scaled positive")
disp((N("S9(3)", sign="LEADING"), "-12"), "leading embedded")
disp((N("S9(4)", "COMP"), "-7"), "binary signed")
disp((N("9(4)", "COMP"), "7"), "binary unsigned")
disp((N("S9(9)", "COMP"), "123456789"), "binary 4 bytes")
disp((N("S9(18)", "COMP"), "-123456789012345678"), "binary 8 bytes")
disp((N("S9(5)V99", "COMP-3"), "-123.45"), "packed scaled")
disp((N("9(3)", "COMP-3"), "123"), "packed unsigned")
disp((N("S9(3)", "COMP-5"), "-12"), "COMP-5")
disp((N("S9(4)V9", "COMP"), "-12.5"), "binary scaled")
disp((X(5), '"AB"'), "alphanumeric")
disp((G(4), txt("A1B2")), "group")
disp((E("ZZ9.99-"), None), "edited")
disp((N("S9(3)V99", sign="TRAILING SEPARATE"), "-1.5"), "trailing separate scaled")
disp((N("9(4)V9", "COMP"), "12.5"), "binary unsigned scaled")
disp((N("S9(4)", "COMP-3"), "-12"), "even-digit packed")

# ------------------------------------------------------------------------------ STRING / UNSTRING / INSPECT


def strcase(items, cob, jav, note="", out=("RCV",), res=False, xfail=None):
    add("ST", items, cob, jav, out=out, res=res, xfail=xfail, note=note)


SP = "Cobol.StringPart"
strcase([("SND", X(8), '"HELLO W"'), ("RCV", X(12), 'ALL "#"')],
        'STRING "AB" DELIMITED BY SIZE SND DELIMITED BY SPACE INTO RCV',
        f'Cobol.string(RCV, null, CS, {SP}.size("AB", CS), {SP}.delimited(SND, " ", CS));', "unfilled part kept")  # fmt: skip
strcase([("SND", X(8), '"A,B,C"'), ("RCV", X(12), 'ALL "#"')],
        'STRING SND DELIMITED BY "," INTO RCV',
        f'Cobol.string(RCV, null, CS, {SP}.delimited(SND, ",", CS));', "up to the first comma")  # fmt: skip
strcase([("SND", X(3), '"XYZ"'), ("RCV", X(8), 'ALL "#"'), ("PTR", N("9(2)"), "4")],
        "STRING SND DELIMITED BY SIZE INTO RCV WITH POINTER PTR",
        f"Cobol.string(RCV, PTR, CS, {SP}.size(SND));", "pointer start and update", out=("RCV", "PTR"))  # fmt: skip
strcase([("SND", X(6), '"ABCDEF"'), ("RCV", X(4), 'ALL "#"'), ("RES", X(8), None)],
        'STRING SND DELIMITED BY SIZE INTO RCV ON OVERFLOW MOVE "O" TO RES END-STRING',
        f'if (Cobol.string(RCV, null, CS, {SP}.size(SND))) Cobol.move("O", RES, CS);', "overflow: what fits transferred", out=("RCV", "RES"))  # fmt: skip
strcase([("SND", X(3), '"XYZ"'), ("RCV", X(8), 'ALL "#"'), ("PTR", N("9(2)"), "0"), ("RES", X(8), None)],
        'STRING SND DELIMITED BY SIZE INTO RCV WITH POINTER PTR ON OVERFLOW MOVE "O" TO RES END-STRING',
        f'if (Cobol.string(RCV, PTR, CS, {SP}.size(SND))) Cobol.move("O", RES, CS);', "pointer 0: overflow, nothing moved", out=("RCV", "PTR", "RES"))  # fmt: skip
strcase([("SND", X(3), '"XYZ"'), ("RCV", X(8), 'ALL "#"'), ("PTR", N("9(2)"), "9"), ("RES", X(8), None)],
        'STRING SND DELIMITED BY SIZE INTO RCV WITH POINTER PTR ON OVERFLOW MOVE "O" TO RES END-STRING',
        f'if (Cobol.string(RCV, PTR, CS, {SP}.size(SND))) Cobol.move("O", RES, CS);', "pointer past the end", out=("RCV", "PTR", "RES"))  # fmt: skip
strcase([("SND", X(6), '"AB--CD"'), ("DLM", X(2), '"--"'), ("RCV", X(8), 'ALL "#"')],
        "STRING SND DELIMITED BY DLM INTO RCV",
        f"Cobol.string(RCV, null, CS, {SP}.delimited(SND, DLM));", "delimiter in an item")  # fmt: skip
strcase([("SND", X(6), '"AB    "'), ("RCV", X(8), 'ALL "#"')],
        'STRING SND DELIMITED BY SIZE "|" DELIMITED BY SIZE INTO RCV',
        f'Cobol.string(RCV, null, CS, {SP}.size(SND), {SP}.size("|", CS));', "trailing spaces transferred")  # fmt: skip

SPC = "Cobol.StringPart"
UN = "Cobol.unstring"
D = "Cobol.Delim"
INTO = "Cobol.Into"
ul3 = [("SND", X(11), '"AB,CD,EF,GH"'), ("F1", X(3), 'ALL "#"'), ("F2", X(3), 'ALL "#"'), ("F3", X(3), 'ALL "#"')]
strcase(ul3, 'UNSTRING SND DELIMITED BY "," INTO F1 F2 F3',
        f'{UN}(SND, null, null, List.of({D}.of(",", false, CS)), CS, {INTO}.of(F1), {INTO}.of(F2), {INTO}.of(F3));',
        "three fields, data left over", out=("F1", "F2", "F3"))  # fmt: skip
strcase([("SND", X(14), '"AB   CD  EF"'), ("F1", X(4), 'ALL "#"'), ("F2", X(4), 'ALL "#"'), ("F3", X(4), 'ALL "#"'), ("RES", X(8), None)],
        'UNSTRING SND DELIMITED BY ALL SPACES INTO F1 F2 F3 ON OVERFLOW MOVE "O" TO RES END-UNSTRING',
        f'if ({UN}(SND, null, null, List.of({D}.of(" ", true, CS)), CS, {INTO}.of(F1), {INTO}.of(F2), {INTO}.of(F3))) Cobol.move("O", RES, CS);',
        "ALL SPACES; trailing spaces make a last empty field?", out=("F1", "F2", "F3", "RES"))  # fmt: skip
strcase([("SND", X(11), '"AB,CD;EF,GH"'), ("F1", X(3), 'ALL "#"'), ("F2", X(3), 'ALL "#"'), ("F3", X(3), 'ALL "#"'),
         ("C1", N("9(2)"), None), ("C2", N("9(2)"), None), ("D1", X(2), 'ALL "#"'), ("D2", X(2), 'ALL "#"'), ("TL", N("9(2)"), "10")],
        'UNSTRING SND DELIMITED BY "," OR ";" INTO F1 DELIMITER IN D1 COUNT IN C1 F2 DELIMITER IN D2 COUNT IN C2 F3 TALLYING IN TL',
        f'{UN}(SND, null, TL, List.of({D}.of(",", false, CS), {D}.of(";", false, CS)), CS, {INTO}.of(F1).delimiterIn(D1).countIn(C1), {INTO}.of(F2).delimiterIn(D2).countIn(C2), {INTO}.of(F3));',
        "OR, DELIMITER IN, COUNT IN, TALLYING", out=("F1", "F2", "F3", "C1", "C2", "D1", "D2", "TL"))  # fmt: skip
strcase([("SND", X(9), '"AB,CD,EF"'), ("F1", X(4), 'ALL "#"'), ("PTR", N("9(2)"), "4")],
        'UNSTRING SND DELIMITED BY "," INTO F1 WITH POINTER PTR',
        f'{UN}(SND, PTR, null, List.of({D}.of(",", false, CS)), CS, {INTO}.of(F1));', "WITH POINTER", out=("F1", "PTR"))  # fmt: skip
strcase([("SND", X(6), '"AB,CD"'), ("F1", X(3), 'ALL "#"'), ("F2", X(3), 'ALL "#"'), ("F3", X(3), 'ALL "#"'), ("TL", N("9(2)"), None)],
        'UNSTRING SND DELIMITED BY "," INTO F1 F2 F3 TALLYING IN TL',
        f'{UN}(SND, null, TL, List.of({D}.of(",", false, CS)), CS, {INTO}.of(F1), {INTO}.of(F2), {INTO}.of(F3));', "fewer fields than INTOs", out=("F1", "F2", "F3", "TL"))  # fmt: skip
strcase([("SND", X(8), '"12,0034,"'), ("F1", N("9(3)"), None), ("F2", N("9(3)V9"), None)],
        'UNSTRING SND DELIMITED BY "," INTO F1 F2',
        f'{UN}(SND, null, null, List.of({D}.of(",", false, CS)), CS, {INTO}.of(F1), {INTO}.of(F2));', "numeric receivers", out=("F1", "F2"))  # fmt: skip
strcase([("SND", X(6), '"ABCDEF"'), ("F1", X(3), 'ALL "#"'), ("F2", X(3), 'ALL "#"')],
        "UNSTRING SND INTO F1 F2",
        f"{UN}(SND, null, null, List.of(), CS, {INTO}.of(F1), {INTO}.of(F2));", "no delimiter: the whole source to the first", out=("F1", "F2"))  # fmt: skip
strcase([("SND", X(8), '"AB<>CD<>"'), ("F1", X(3), 'ALL "#"'), ("F2", X(3), 'ALL "#"'), ("F3", X(3), 'ALL "#"')],
        'UNSTRING SND DELIMITED BY "<>" INTO F1 F2 F3',
        f'{UN}(SND, null, null, List.of({D}.of("<>", false, CS)), CS, {INTO}.of(F1), {INTO}.of(F2), {INTO}.of(F3));', "two-character delimiter, source ends on one", out=("F1", "F2", "F3"))  # fmt: skip


def un3(sd, init, dl, jdl, note, extra_items=(), res=False, ptr=None):
    items = [("SND", X(len(sd)), f'"{sd}"'), ("F1", X(3), 'ALL "#"'), ("F2", X(3), 'ALL "#"'), ("F3", X(3), 'ALL "#"')]
    items += list(extra_items)
    ptrs = "PTR" if ptr is not None else "null"
    wp = " WITH POINTER PTR" if ptr is not None else ""
    cobol = f"UNSTRING SND DELIMITED BY {dl} INTO F1 F2 F3{wp}"
    jav = f"{UN}(SND, {ptrs}, null, List.of({jdl}), CS, {INTO}.of(F1), {INTO}.of(F2), {INTO}.of(F3));"
    if res:
        cobol += ' ON OVERFLOW MOVE "O" TO RES END-UNSTRING'
        jav = f'if ({jav[:-1]}) Cobol.move("O", RES, CS);'
        items.append(("RES", X(8), None))
    if ptr is not None:
        items.append(("PTR", N("9(2)"), str(ptr)))
    strcase(
        items,
        cobol,
        jav,
        note,
        out=("F1", "F2", "F3") + (("RES",) if res else ()) + (("PTR",) if ptr is not None else ()),
    )


un3("A,,B", None, '","', f'{D}.of(",", false, CS)', "an empty field between delimiters")
un3(",AB", None, '","', f'{D}.of(",", false, CS)', "a leading delimiter")
un3("A,,,B", None, 'ALL ","', f'{D}.of(",", true, CS)', "ALL collapses a run of delimiters")
un3("A,B,C,D", None, '","', f'{D}.of(",", false, CS)', "OVERFLOW: more data than receivers", res=True)
un3("A,B,C", None, '","', f'{D}.of(",", false, CS)', "no overflow when the data ends with the last field", res=True)
un3("A,B", None, '","', f'{D}.of(",", false, CS)', "invalid pointer: overflow, nothing moved", res=True, ptr=0)
un3("A,B,C,D", None, '","', f'{D}.of(",", false, CS)', "pointer in the middle", res=True, ptr=3)
un3(
    "ABCDEFGH",
    None,
    '"CD" OR "F"',
    f'{D}.of("CD", false, CS), {D}.of("F", false, CS)',
    "two delimiters, first match wins by position",
)
un3("A,B,", None, '","', f'{D}.of(",", false, CS)', "trailing delimiter then end of data")
strcase([("SND", X(6), '"ABCDEF"'), ("RCV", X(8), 'ALL "#"'), ("PTR", N("9(2)"), "7"), ("RES", X(8), None)],
        'STRING SND DELIMITED BY SIZE INTO RCV WITH POINTER PTR ON OVERFLOW MOVE "O" TO RES END-STRING',
        f'if (Cobol.string(RCV, PTR, CS, {SPC}.size(SND))) Cobol.move("O", RES, CS);', "overflow after a partial transfer: pointer", out=("RCV", "PTR", "RES"))  # fmt: skip
strcase([("SND", X(6), '"AB,CD "'), ("RCV", X(8), 'ALL "#"')],
        'STRING SND DELIMITED BY "," SND DELIMITED BY SPACE INTO RCV',
        f'Cobol.string(RCV, null, CS, {SPC}.delimited(SND, ",", CS), {SPC}.delimited(SND, " ", CS));', "the same source twice")  # fmt: skip
strcase([("SND", X(6), '"AB,CD "'), ("RCV", X(8), 'ALL "#"')],
        'STRING SND DELIMITED BY ", " INTO RCV',
        f'Cobol.string(RCV, null, CS, {SPC}.delimited(SND, ", ", CS));', "a two-character delimiter not present")  # fmt: skip

INS = "Cobol.inspect"
CL = "Cobol.Clause"
MO = "Cobol.Mode"


def ins(items, cob, jav, note="", out=("SND",), xfail=None):
    add("IN", items, cob, jav, out=out, xfail=xfail, note=note)


ins([("SND", X(10), '"BANANA BAR"'), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR ALL "A"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.ALL, "A", CS));', "ALL", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(10), '"BANANA BAR"'), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR CHARACTERS BEFORE INITIAL " "',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.CHARACTERS, null, CS).before(" ", CS));', "CHARACTERS BEFORE", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(8), '"00012300"'), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR LEADING "0"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.LEADING, "0", CS));', "LEADING", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(8), '"AABAABAA"'), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR ALL "AA" AFTER INITIAL "B"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.ALL, "AA", CS).after("B", CS));', "ALL AFTER", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(10), '"BANANA BAR"')], 'INSPECT SND REPLACING ALL "A" BY "o"',
    f'{INS}(SND, CS, {CL}.replace({MO}.ALL, "A", "o", CS));', "REPLACING ALL")  # fmt: skip
ins([("SND", X(8), '"00012300"')], 'INSPECT SND REPLACING LEADING "0" BY SPACE',
    f'{INS}(SND, CS, {CL}.replace({MO}.LEADING, "0", " ", CS));', "REPLACING LEADING")  # fmt: skip
ins([("SND", X(10), '"BANANA BAR"')], 'INSPECT SND REPLACING FIRST "A" BY "x"',
    f'{INS}(SND, CS, {CL}.replace({MO}.FIRST, "A", "x", CS));', "REPLACING FIRST")  # fmt: skip
ins([("SND", X(10), '"AB.CD.EF  "')], 'INSPECT SND REPLACING CHARACTERS BY "*" AFTER INITIAL "."',
    f'{INS}(SND, CS, {CL}.replace({MO}.CHARACTERS, null, "*", CS).after(".", CS));', "CHARACTERS AFTER")  # fmt: skip
ins([("SND", X(10), '"AB.CD.EF  "')], 'INSPECT SND REPLACING ALL "." BY "-" BEFORE INITIAL "EF"',
    f'{INS}(SND, CS, {CL}.replace({MO}.ALL, ".", "-", CS).before("EF", CS));', "ALL BEFORE")  # fmt: skip
ins([("SND", X(10), '"ab cd ef g"')], 'INSPECT SND CONVERTING "abcdefgh" TO "ABCDEFGH"',
    f'{INS}(SND, CS, {CL}.converting("abcdefgh", "ABCDEFGH", CS));', "CONVERTING")  # fmt: skip
ins([("SND", X(10), '"ab cd ef g"'), ], 'INSPECT SND CONVERTING "abcdefgh" TO "ABCDEFGH" AFTER INITIAL " "',
    f'{INS}(SND, CS, {CL}.converting("abcdefgh", "ABCDEFGH", CS).after(" ", CS));', "CONVERTING AFTER")  # fmt: skip
ins([("SND", X(10), '"AABBAABBAA"'), ("CNT", N("9(2)"), None)],
    'INSPECT SND TALLYING CNT FOR ALL "AB" REPLACING ALL "A" BY "x"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.ALL, "AB", CS), {CL}.replace({MO}.ALL, "A", "x", CS));',
    "TALLYING and REPLACING: the earlier phrase takes the characters", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(10), '"00120034 "'), ("C1", N("9(2)"), None), ("C2", N("9(2)"), None)],
    'INSPECT SND TALLYING C1 FOR ALL "0" C2 FOR LEADING "0"',
    f'{INS}(SND, CS, {CL}.tally(C1, {MO}.ALL, "0", CS), {CL}.tally(C2, {MO}.LEADING, "0", CS));',
    "two counters: LEADING after ALL finds the characters already taken", out=("SND", "C1", "C2"))  # fmt: skip
ins([("SND", X(10), '"AAAAAAAAAA"')], 'INSPECT SND REPLACING ALL "AA" BY "BC" AFTER INITIAL "Q"',
    f'{INS}(SND, CS, {CL}.replace({MO}.ALL, "AA", "BC", CS).after("Q", CS));', "AFTER INITIAL not found: nothing replaced")  # fmt: skip
ins([("SND", X(10), '"AAAAAAAAAA"'), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR ALL "AA" BEFORE INITIAL "Q"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.ALL, "AA", CS).before("Q", CS));', "BEFORE INITIAL not found: whole item", out=("SND", "CNT"))  # fmt: skip


ins([("SND", X(10), '"ABABABAB  "')], 'INSPECT SND REPLACING ALL "AB" BY "XY" ALL "A" BY "Z" ALL "BA" BY "QQ"',
    f'{INS}(SND, CS, {CL}.replace({MO}.ALL, "AB", "XY", CS), {CL}.replace({MO}.ALL, "A", "Z", CS), {CL}.replace({MO}.ALL, "BA", "QQ", CS));',
    "overlapping REPLACING clauses: the earlier takes the characters")  # fmt: skip
ins([("SND", X(10), '"AB.CD.EF.G"'), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR CHARACTERS AFTER INITIAL "." BEFORE INITIAL "G"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.CHARACTERS, null, CS).after(".", CS).before("G", CS));', "BEFORE and AFTER together", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(8), '"00100200"')], 'INSPECT SND REPLACING LEADING "0" BY "9" AFTER INITIAL "1"',
    f'{INS}(SND, CS, {CL}.replace({MO}.LEADING, "0", "9", CS).after("1", CS));', "LEADING after an INITIAL")  # fmt: skip
ins([("SND", X(8), '"AAAAAAAA"')], 'INSPECT SND REPLACING FIRST "AA" BY "BB" ALL "A" BY "C"',
    f'{INS}(SND, CS, {CL}.replace({MO}.FIRST, "AA", "BB", CS), {CL}.replace({MO}.ALL, "A", "C", CS));', "FIRST then ALL")  # fmt: skip
ins([("SND", X(8), '"A1B2C3D4"')], 'INSPECT SND CONVERTING "1234" TO "ABCD" BEFORE INITIAL "C"',
    f'{INS}(SND, CS, {CL}.converting("1234", "ABCD", CS).before("C", CS));', "CONVERTING BEFORE")  # fmt: skip
ins([("SND", N("9(5)"), "10200"), ("CNT", N("9(2)"), None)], 'INSPECT SND TALLYING CNT FOR ALL "0"',
    f'{INS}(SND, CS, {CL}.tally(CNT, {MO}.ALL, "0", CS));', "a numeric DISPLAY target", out=("SND", "CNT"))  # fmt: skip
ins([("SND", X(8), '"ABCABC  "')], 'INSPECT SND REPLACING CHARACTERS BY "-" BEFORE INITIAL "C"',
    f'{INS}(SND, CS, {CL}.replace({MO}.CHARACTERS, null, "-", CS).before("C", CS));', "CHARACTERS BEFORE")  # fmt: skip


# ----------------------------------------------------------------------------------------- the generators


def _cob_name(cid: str, name: str) -> str:
    return f"{cid}-{name}"


def cobol_program() -> str:
    L = []
    w = L.append
    w("IDENTIFICATION DIVISION.")
    w("PROGRAM-ID. MAIN.")
    w("DATA DIVISION.")
    w("WORKING-STORAGE SECTION.")
    w("01 WS-LEN PIC 9(4).")
    for c in CASES:
        names = [n for n, _, _ in c.items]
        for name, spec, init in c.items:
            full = _cob_name(c.cid, name)
            if isinstance(init, bytes):
                w(f'01 {full}-R PIC X({spec.length()}) VALUE X"{init.hex()}".')
                if spec.kind == "G":
                    w(f"01 {full} REDEFINES {full}-R.")
                    w(f"   05 FILLER PIC X({spec.length()}).")
                elif spec.kind == "T":
                    w(f"01 {full} REDEFINES {full}-R.")
                    w(f"   05 {full}-EL OCCURS {spec.n} PIC X({spec.elem}).")
                else:
                    w(f"01 {full} REDEFINES {full}-R {spec.decl()}.")
            elif spec.kind == "G":
                w(f"01 {full}.")
                w(f"   05 FILLER PIC X({spec.length()}).")
            elif spec.kind == "T":
                w(f"01 {full}.")
                w(f"   05 {full}-EL OCCURS {spec.n} PIC X({spec.elem}).")
            else:
                val = f" VALUE {init}" if init is not None else ""
                w(f"01 {full} {spec.decl()}{val}.")
    w("PROCEDURE DIVISION.")
    for c in CASES:
        names = [n for n, _, _ in c.items]
        sub = re.compile(r"\b(" + "|".join(sorted(names, key=len, reverse=True)) + r")\b")
        w(f"*> {c.cid} {c.note}")

        def dump(kind):
            for name in dict.fromkeys(list(names)):
                full = _cob_name(c.cid, name)
                tag = f"{kind} {c.cid} {name}".ljust(24)
                w(f"    MOVE FUNCTION LENGTH({full}) TO WS-LEN")
                w(f'    CALL "DUMPER" USING "{tag}" {full} WS-LEN')

        dump("I")
        stmt = c.cob.replace("{CID}", c.cid)
        stmt = sub.sub(lambda m: _cob_name(c.cid, m.group(1)), stmt)
        w("    " + stmt)
        dump("A")
    w("    STOP RUN.")
    w("END PROGRAM MAIN.")
    w("""IDENTIFICATION DIVISION.
PROGRAM-ID. DUMPER.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 HEXDIGITS PIC X(16) VALUE "0123456789ABCDEF".
01 I PIC 9(4).
01 B PIC 9(4).
01 HI PIC 9(4).
01 LO PIC 9(4).
01 OP PIC 9(4).
01 OUTLINE PIC X(2048).
LINKAGE SECTION.
01 LK-TAG PIC X(24).
01 LK-DATA PIC X(1024).
01 LK-LEN PIC 9(4).
PROCEDURE DIVISION USING LK-TAG LK-DATA LK-LEN.
    MOVE 1 TO OP
    PERFORM VARYING I FROM 1 BY 1 UNTIL I > LK-LEN
        COMPUTE B = FUNCTION ORD(LK-DATA(I:1)) - 1
        DIVIDE B BY 16 GIVING HI REMAINDER LO
        MOVE HEXDIGITS(HI + 1:1) TO OUTLINE(OP:1)
        MOVE HEXDIGITS(LO + 1:1) TO OUTLINE(OP + 1:1)
        ADD 2 TO OP
    END-PERFORM
    COMPUTE B = 2 * LK-LEN
    DISPLAY LK-TAG "|" OUTLINE(1:B)
    GOBACK.
END PROGRAM DUMPER.
""")
    return "\n".join(L) + "\n"


def java_main(init_pkg: str) -> str:
    L = []
    w = L.append
    w(f"package {PKG};")
    w(
        """import java.io.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import {pkg}.cobolrt.*;

public final class Main {
    static final Charset CS = StandardCharsets.ISO_8859_1;
    static Map<String, byte[]> init = new HashMap<>();

    static byte[] unhex(String h) {
        byte[] b = new byte[h.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        return b;
    }

    static Storage st(String id, String name) {
        byte[] b = init.get(id + " " + name);
        Storage s = new Storage(b.length);
        System.arraycopy(b, 0, s.bytes, 0, b.length);
        return s;
    }

    static void dump(PrintStream out, String id, String name, Field f) {
        StringBuilder h = new StringBuilder();
        for (byte b : f.raw()) h.append(String.format("%02X", b & 0xFF));
        out.println("A " + id + " " + name + "|" + h);
    }
""".replace("{pkg}", PKG)
    )
    for c in CASES:
        w(f"    static void {c.cid}(PrintStream out) throws Exception {{")
        for name, spec, _ in c.items:
            w(f'        Storage {name}_s = st("{c.cid}", "{name}");')
            w(f"        Field {name} = {spec.java(name + '_s')};")
        w("        " + c.jav.replace("{CID}", c.cid))
        for name, _, _ in c.items:
            w(f'        dump(out, "{c.cid}", "{name}", {name});')
        w("    }")
    w(
        """
    public static void main(String[] args) throws Exception {
        for (String line : Files.readAllLines(Paths.get(args[0]), StandardCharsets.ISO_8859_1)) {
            String[] p = line.split(" ");
            init.put(p[0] + " " + p[1], unhex(p[2]));
        }
        PrintStream out = new PrintStream(new FileOutputStream(FileDescriptor.out), false, "ISO-8859-1");
"""
    )
    for c in CASES:
        w(f'        try {{ {c.cid}(out); }} catch (Throwable t) {{ out.println("E|{c.cid}|" + t); }}')
    w("        out.flush();\n    }\n}")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------------- run both


def _parse(stdout: bytes) -> dict[str, dict[str, str]]:
    """{case id: {key: value}} from the program's lines (I|, A|, D|, E|)."""
    res: dict[str, dict[str, str]] = {}
    init: dict[str, str] = {}
    for raw in stdout.decode("latin-1").split("\n"):
        line = raw.rstrip("\r")
        kind, _, rest = line.partition("|")
        if kind.startswith("I "):
            cid, name = kind.split()[1:3]
            init[f"{cid} {name}"] = rest.strip()
        elif kind.startswith("A "):
            cid, name = kind.split()[1:3]
            res.setdefault(cid, {})[name] = rest.strip()
        elif kind == "D":
            cid, _, text = rest.partition("|")
            res.setdefault(cid, {})["DISPLAY"] = text
        elif kind == "E":
            cid, _, text = rest.partition("|")
            res.setdefault(cid, {})["ERROR"] = text
    res["__init__"] = init  # type: ignore[assignment]
    return res


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    work = tmp_path_factory.mktemp("cobolrt")
    (work / "M.cbl").write_text(cobol_program(), encoding="latin-1")
    shutil.copy(eq.FAULTS_DIR / "ggdisplay.c", work / "ggdisplay.c")
    script = (
        "set -e; gcc -shared -fPIC -O2 -o g.so ggdisplay.c -ldl && cobc -x -free -std=ibm -fsign=EBCDIC -o m M.cbl "
        "&& LD_PRELOAD=/w/g.so ./m > out.txt 2> err.txt || { cat err.txt; exit 1; }"
    )
    proc = subprocess.run(  # noqa: S603
        ["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", eq.IMAGE, "bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cobol = _parse((work / "out.txt").read_bytes())
    init = cobol.pop("__init__")
    # Java: the runtime with the placeholder package replaced, then Main
    src = work / "src"
    (src / PKG / "cobolrt").mkdir(parents=True)
    for f in RT.glob("*.java"):
        (src / PKG / "cobolrt" / f.name).write_text(f.read_text().replace("__PACKAGE__", PKG), encoding="utf-8")
    (src / PKG / "Main.java").write_text(java_main(PKG), encoding="utf-8")
    classes = work / "classes"
    classes.mkdir()
    files = [str(p) for p in src.rglob("*.java")]
    javac = subprocess.run(  # noqa: S603
        [str(JAVA_BIN / "javac"), "-encoding", "UTF-8", "-d", str(classes), *files],
        capture_output=True,
        text=True,
        check=False,
    )
    assert javac.returncode == 0, javac.stderr[:4000]
    (work / "init.txt").write_text("\n".join(f"{k} {v}" for k, v in init.items()) + "\n", encoding="latin-1")
    java = subprocess.run(  # noqa: S603
        [str(JAVA_BIN / "java"), "-cp", str(classes), f"{PKG}.Main", str(work / "init.txt")],
        capture_output=True,
        check=False,
    )
    assert java.returncode == 0, java.stderr.decode()[:2000]
    (work / "java.txt").write_bytes(java.stdout)
    if os.environ.get("COBOLRT_KEEP"):  # keep the program, its output and the Java output for inspection
        shutil.copytree(work, os.environ["COBOLRT_KEEP"], dirs_exist_ok=True)
    return cobol, _parse(java.stdout)


def _param(c: Case):
    marks = [pytest.mark.xfail(reason=c.xfail, strict=True)] if c.xfail else []
    return pytest.param(c, id=f"{c.cid}-{c.note[:40].replace(' ', '_')}", marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_case_matches_gnucobol(runs, case):
    cobol, java = runs
    want = cobol.get(case.cid)
    got = java.get(case.cid)
    assert want is not None, f"{case.cid}: GnuCOBOL printed nothing"
    assert got is not None, f"{case.cid}: Java printed nothing"
    assert "ERROR" not in got, got.get("ERROR")
    for name in [n for n, _, _ in case.items]:
        assert got.get(name) == want.get(name), (
            f"{case.cid} {name} ({case.note}): java {got.get(name)} != cobol {want.get(name)}"
        )
    if case.disp:
        assert got.get("DISPLAY") == want.get("DISPLAY"), (
            f"{case.cid} DISPLAY: java {got.get('DISPLAY')!r} != cobol {want.get('DISPLAY')!r}"
        )


def test_the_matrix_is_large_enough():
    by = {}
    for c in CASES:
        by[c.cid[:2]] = by.get(c.cid[:2], 0) + 1
    assert by["MV"] + by["ML"] + by["MF"] + by["MA"] + by["MR"] >= 40
    assert by["AR"] >= 20 and by["CP"] >= 15 and by["CL"] >= 10 and by["DP"] >= 15
    assert by["ST"] + by["IN"] >= 10
