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
from test_det_nondigit_binary import FLAGS, IMAGE, PKG, _det, _java  # noqa: E402

pytestmark = pytest.mark.slow(
    reason="the first java test of a CI split part pays the one-time javac of the cobolrt runtime: 12-17 s on a runner (#5668)"
)

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
    "01 PK PIC S9(7) COMP-3.", "01 PKN REDEFINES PK PIC 9(9) COMP.",
    "01 UPK PIC 9(6) COMP-3.", "01 UPKN REDEFINES UPK PIC 9(9) COMP.",
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
# a receiver of the sender's own shape: cobc moves it with a memcpy, nothing converted (COCRDUPC's CVV)
OPS.append(["MOVE @ TO OWN", "DISPLAY '#>OWN ' OWNX"])
# the operations that print the sender's bytes as they are (a byte >= X'80' in a digit position stays out of them)
# the zoned and edited receivers; packed ones as a COMP number (COMP-5 bytes are refused, C7)
RAW = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, len(OPS) - 1}


def _program(kind: str) -> str:
    pic, ln = KINDS[kind]
    data = DATA + [
        f"01 R PIC X({ln}).",
        f"01 S REDEFINES R {pic}.",
        f"01 OWN {pic}.",
        f"01 OWNX REDEFINES OWN PIC X({ln}).",
    ]
    proc = []
    for n, b in enumerate(CASES[kind], 1):
        label = f"{kind}{n}"
        high = any(c >= 0x80 for c in (b[1:-1] if kind in ("TS", "LS") else b))
        high = high and not (kind in ("T", "TS") and b[-1] >= 0x80 and all(c < 0x80 for c in b[:-1]))
        high = high and not (kind in ("L", "LS") and b[0] >= 0x80 and all(c < 0x80 for c in b[1:]))
        for i, op in enumerate(OPS):
            if (high and i in RAW) or (i == len(OPS) - 1 and any(c >= 0x80 for c in b)):
                continue
            proc.append(f"MOVE X'{b.hex().upper()}' TO R")
            proc += [x.replace("@", "S").replace("#", label) for x in op]
            if any(c >= 0x80 for c in b):
                proc.append("INSPECT R CONVERTING X'FF' TO '#'")
            proc.append(f"DISPLAY '{label}af ' R")
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."]  # fmt: skip
    lines += [f"       {x}" for x in data] + ["       PROCEDURE DIVISION."] + [f"           {x}" for x in proc]
    return "\n".join([*lines, "           GOBACK.", ""])


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


# ---------------------------------------------------------------------------------------------------------------
# #4692: the RECEIVER holds the non-digit. ADD / SUBTRACT / MULTIPLY / DIVIDE read their receiver before they store.
# Measured: cobc 3.1.2 (`cob_add_int`, `cob_add`) reads such a receiver through cob_decimal_set_display, as an operand
# (not in place, as the issue assumed), so the det runtime's old read agreed with it. IBM documents no result for it
# (ZONEDATA(PFD), the default, assumes valid zone bits; PI57769 says only that under NOPFD|MIG an ADD corrects invalid
# zone bits), so the port REFUSES by name (Cobol.receiverNum, register C11); a receiver that is only overwritten
# (MOVE, GIVING) or that reads as an operand (COMPUTE y = y + 1, C11's operand rule) is unchanged.
# ---------------------------------------------------------------------------------------------------------------
RECEIVER_EXPECTED = Path(__file__).with_name("nondigit_zoned_receiver_expected.txt")
RCASES = {
    "U": [b"    ", b"12A4", b"1 34", b"\0\0\0\0", b"12\xff4", b"1234", b"0099"],
    "T": [b"    ", b"12A4", b"123 ", b"123}", b"1234", b"\0\0\0\0", b"123!", b"123J"],
    "L": [b"    ", b" 123", b"{123", b"1234", b"}123", b"!123"],
    "TS": [b"12A4+", b"12 4-", b"1234 ", b"1234+", b"1234-", b"    +"],
    "LS": [b"+12A4", b"-12 4", b" 1234", b"+1234", b"-1234", b"+    "],
}  # fmt: skip
# operations that read the receiver (refused when it holds a non-digit) and ones that do not (measured, proven)
READS = ["ADD 1 TO V", "SUBTRACT 1 FROM V", "ADD 1 TO V ROUNDED", "ADD W TO V", "MULTIPLY 2 BY V", "DIVIDE 2 INTO V"]
KEEPS = ["MOVE 7 TO V", "ADD 1 TO V GIVING OT", "COMPUTE V = V + 1", "COMPUTE V = W + 1"]


def _dirty(kind: str, b: bytes) -> bool:
    """Whether the bytes hold a non-digit in a digit position or a sign byte that is no sign (`{` `A`-`I` `}` `J`-`R`
    or a digit; a separate sign is + or -)."""
    t = b.decode("latin-1")
    if kind in ("TS", "LS"):
        sign, t = (t[-1], t[:-1]) if kind == "TS" else (t[0], t[1:])
        return sign not in "+-" or not t.isdigit()
    if kind == "T":
        sign, t = t[-1], t[:-1]
    elif kind == "L":
        sign, t = t[0], t[1:]
    else:
        sign = "0"
    return not (t.isdigit() and (sign.isdigit() or sign in "{}ABCDEFGHIJKLMNOPQR"))


def _rprogram(kind: str, ops: list[str], cases: list[bytes]) -> str:
    pic, ln = KINDS[kind]
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION.", f"       01 R PIC X({ln}).", f"       01 V REDEFINES R {pic}.",
             "       01 OT PIC 9(5).", "       01 W PIC 9(9) VALUE 3.", "       PROCEDURE DIVISION."]  # fmt: skip
    for n, b in enumerate(cases, 1):
        for i, op in enumerate(ops):
            lines += [f"           MOVE X'{b.hex().upper()}' TO R", "           MOVE 0 TO OT", f"           {op}",
                      "           INSPECT R CONVERTING X'FF' TO '#'", f"           DISPLAY '{kind}{n}.{i} ' R ' ' OT"]  # fmt: skip
    return "\n".join([*lines, "           GOBACK.", ""])


def _rcases(kind: str, dirty: bool) -> list[bytes]:
    return [b for b in RCASES[kind] if _dirty(kind, b) == dirty]


def _rexpected() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = ""
    for line in RECEIVER_EXPECTED.read_text().split("\n"):
        if line.startswith("== "):
            key = line[3:]
            out[key] = []
        elif key and line != "== end":
            out[key].append(line)
    return out


def _rcobc(kind: str, trunc: str, work: Path) -> str:
    # digit-only receivers run every operation, a non-digit one only those that do not read it
    src = _rprogram(kind, READS, _rcases(kind, False)).replace("           GOBACK.\n", "")
    keep = _rprogram(kind, KEEPS, _rcases(kind, True) + _rcases(kind, False))
    keep = keep.split("PROCEDURE DIVISION.\n", 1)[1]
    (work / "ndb.cbl").write_text(src + keep)
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          f"cobc -x -std=ibm -fsign=EBCDIC {FLAGS[trunc]} ndb.cbl -o ndb 2>&1 && ./ndb"],
                         capture_output=True, check=False)  # fmt: skip
    text = run.stdout.decode("latin-1")
    assert run.returncode == 0, text
    return text


def _rsource(kind: str) -> str:
    src = _rprogram(kind, READS, _rcases(kind, False)).replace("           GOBACK.\n", "")
    keep = _rprogram(kind, KEEPS, _rcases(kind, True) + _rcases(kind, False))
    return src + keep.split("PROCEDURE DIVISION.\n", 1)[1]


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("trunc", ["STD", "BIN"])
@pytest.mark.parametrize("kind", list(KINDS))
def test_receiver_digit_only_and_overwritten_is_the_oracles(kind, trunc, tmp_path):
    """Digit-only receivers of every reading operation, and non-digit receivers of the operations that only overwrite
    them (MOVE, GIVING) or read them as an operand (COMPUTE), print what cobc printed."""
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_rsource(kind), tmp_path, trunc)
    assert run.returncode == 0, run.stderr
    assert _esc(run.stdout) == _rexpected()[f"{kind} {trunc}"]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker (EQUIVALENCE_E2E=1)")  # fmt: skip
@pytest.mark.parametrize("trunc", ["STD", "BIN"])
@pytest.mark.parametrize("kind", list(KINDS))
def test_the_receiver_expected_lines_are_cobcs(kind, trunc, tmp_path):
    (tmp_path / "ndb.cbl").write_text(_rsource(kind))
    assert _esc(_rcobc(kind, trunc, tmp_path)) == _rexpected()[f"{kind} {trunc}"]


# a first byte of each shape's dirty receiver that is cheap to run: every reading operation on the unsigned shape,
# the add on the others
REFUSED = [("U", op, b"    ") for op in READS] + [(k, "ADD 1 TO V", RCASES[k][1]) for k in KINDS if k != "U"]


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize(("kind", "op", "data"), REFUSED)
def test_a_non_digit_receiver_is_refused_by_name(kind, op, data, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_rprogram(kind, [op], [data]), tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr, run.stderr
    assert "arithmetic whose receiver is a zoned item holding a non-digit is not modelled" in run.stderr, run.stderr


# ---------------------------------------------------------------------------------------------------------------
# #4692: the other statements that read an item before they store it -- an INSPECT TALLYING counter, an UNSTRING
# TALLYING IN counter and a STRING / UNSTRING POINTER -- are the receiver class too. A zoned item holding a non-digit
# there is refused by name (Cobol.counterNum, register C11), as the receiver of ADD is; a digit-only one counts as ever.
# ---------------------------------------------------------------------------------------------------------------
COUNTER_OPS = {
    "INSPECT": ("INSPECT S TALLYING V FOR ALL 'A'", "4"),
    "INSPECT-CHARS": ("INSPECT S TALLYING V FOR CHARACTERS", "8"),
    "UNSTRING-TALLY": ("UNSTRING S DELIMITED BY ',' INTO D1 D2 TALLYING IN V", "2"),
    "UNSTRING-PTR": ("UNSTRING S DELIMITED BY ',' INTO D1 D2 WITH POINTER V", "6"),
    "STRING-PTR": ("STRING 'XY' DELIMITED BY SIZE INTO D1 WITH POINTER V", "3"),
}  # fmt: skip


def _cprogram(kind: str, op: str, data: bytes) -> str:
    pic, ln = KINDS[kind]
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION.", f"       01 R PIC X({ln}).", f"       01 V REDEFINES R {pic}.",
             "       01 S PIC X(8) VALUE 'A,AA,A  '.", "       01 D1 PIC X(8).", "       01 D2 PIC X(8).",
             "       PROCEDURE DIVISION.", f"           MOVE X'{data.hex().upper()}' TO R", f"           {op}",
             "           DISPLAY 'R=' R", "           GOBACK.", ""]  # fmt: skip
    return "\n".join(lines)


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("op", list(COUNTER_OPS))
@pytest.mark.parametrize("kind", list(KINDS))
def test_a_non_digit_counter_or_pointer_is_refused_by_name(kind, op, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    data = _rcases(kind, True)[1]  # one letter-bearing case per shape (the first is spaces / a bad sign)
    run = _det(_cprogram(kind, COUNTER_OPS[op][0], data), tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr, (data, run.stderr)
    assert "pointer or tallying counter that is a zoned item holding a non-digit is not modelled" in run.stderr


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("op", list(COUNTER_OPS))
def test_a_digit_only_counter_or_pointer_counts_as_ever(op, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    start = b"0001" if op.endswith("PTR") else b"0000"
    run = _det(_cprogram("U", COUNTER_OPS[op][0], start), tmp_path, "STD")
    assert run.returncode == 0, run.stderr
    want = int(COUNTER_OPS[op][1])
    assert f"R={want:04d}" in run.stdout.replace("\r", ""), (run.stdout, want)


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("op", ["ADD 1 TO V", "ADD W TO V", "SUBTRACT 1 FROM V", "MULTIPLY 2 BY V"])
def test_a_plain_item_cleared_to_spaces_is_refused_as_a_receiver(op, tmp_path):
    """The item the translator may lift (no REDEFINES, named plainly): `MOVE SPACES TO V` then the statement."""
    pytest.importorskip("tree_sitter_language_pack")
    src = "\n".join(["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
                     "       WORKING-STORAGE SECTION.", "       01 V PIC 9(4).", "       01 W PIC 9(4) VALUE 5.",
                     "       PROCEDURE DIVISION.", "           MOVE SPACES TO V", f"           {op}",
                     "           DISPLAY V", "           GOBACK.", ""])  # fmt: skip
    run = _det(src, tmp_path, "STD")
    assert run.returncode != 0 and "receiver is a zoned item holding a non-digit is not modelled" in run.stderr


# #4692: the other forms of a statement that reads its receiver before it stores: ON SIZE ERROR, ROUNDED + SIZE ERROR,
# several receivers, SUBTRACT ROUNDED. Each is refused on a dirty receiver exactly as the plain form is.
CHECKED_OPS = ["ADD 1 TO V ON SIZE ERROR DISPLAY 'E'", "SUBTRACT 1 FROM V ROUNDED ON SIZE ERROR DISPLAY 'E'",
               "ADD 1 TO OT V", "ADD W 1 TO V", "SUBTRACT W 1 FROM V"]  # fmt: skip


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("op", CHECKED_OPS)
@pytest.mark.parametrize("kind", list(KINDS))
def test_a_non_digit_receiver_is_refused_in_every_form_of_the_statement(kind, op, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_rprogram(kind, [op], [RCASES[kind][1]]), tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr, run.stderr
    assert "receiver is a zoned item holding a non-digit is not modelled" in run.stderr, run.stderr


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("verb", ["ADD", "SUBTRACT"])
def test_a_corresponding_receiver_is_refused_at_translation(verb, tmp_path):
    """ADD / SUBTRACT CORRESPONDING is not translated at all, so no dirty group member can reach its read."""
    pytest.importorskip("tree_sitter_language_pack")
    prep = "TO" if verb == "ADD" else "FROM"
    src = "\n".join(["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
                     "       WORKING-STORAGE SECTION.", "       01 G1.", "          05 A PIC 9(4).",
                     "       01 G2.", "          05 A PIC 9(4).",
                     "       PROCEDURE DIVISION.", "           MOVE SPACES TO G2", f"           {verb} CORRESPONDING G1 {prep} G2",
                     "           GOBACK.", ""])  # fmt: skip
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "NDB.cbl").write_text(src)
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "NDB.cbl", [], "public class NdbService {\n}\n", PKG, None, tmp_path / "project")
    assert any("CORRESPONDING" in h for h in r.stats["holes"]), r.stats["holes"]  # a hole, not a translation


# ---------------------------------------------------------------------------------------------------------------
# #4692 / #4685: a zoned SENDER with a P position holding a non-digit. cobc 3.1.2 (measured) hangs on `MOVE` of a left-P
# one (VPP99) to a binary item and computes a right-P one (99PP) by no explainable rule (`ADD S TO DS` of two spaces
# is 17595-); IBM documents no result. Refused by name on every read; a digit-only P item is unchanged (PSCALE in
# test_det_programs.py).
# ---------------------------------------------------------------------------------------------------------------
PICS = ["PIC 99PP", "PIC S99PP", "PIC VPP99", "PIC SVPP99"]
PREADS = [
    "MOVE S TO DU",
    "MOVE S TO PK",
    "MOVE S TO BN",
    "MOVE S TO E1",
    "ADD S TO DS",
    "SUBTRACT S FROM DS",
    "COMPUTE DS = S + 1",
    "COMPUTE BN = S",
    "IF S = 0 DISPLAY 'z' END-IF",
    "IF S > 5 DISPLAY 'g' END-IF",
    "MULTIPLY S BY DS",
    "MULTIPLY 2 BY S GIVING DS",
    "DIVIDE S INTO DS",
    "DIVIDE DS BY S GIVING DU",
]


def _pprogram(pic: str, op: str, data: bytes) -> str:
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION.", "       01 R PIC X(2).", f"       01 S REDEFINES R {pic}.",
             "       01 DU PIC 9(7).", "       01 DS PIC S9(7).", "       01 PK PIC S9(7) COMP-3.",
             "       01 BN PIC S9(9) COMP.", "       01 E1 PIC Z(6)9.", "       01 X PIC X(6).", "       01 N PIC 9(4).",
             "       PROCEDURE DIVISION.",
             f"           MOVE X'{data.hex().upper()}' TO R", f"           {op}", "           GOBACK.", ""]  # fmt: skip
    return "\n".join(lines)


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("pic", PICS)
@pytest.mark.parametrize("op", PREADS)
def test_a_p_scaled_non_digit_sender_is_refused_by_name(pic, op, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    data = b"1!" if pic.startswith(("PIC S", "PIC SV")) else b"1A"
    run = _det(_pprogram(pic, op, data), tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr, run.stderr
    assert "P scaling position" in run.stderr and "is not modelled" in run.stderr, run.stderr


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("pic", PICS)
def test_a_p_scaled_digit_only_sender_is_read_as_ever(pic, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    src = _pprogram(pic, "ADD S TO DS", b"12").replace(
        "           GOBACK.", "           DISPLAY DS\n           GOBACK."
    )
    run = _det(src, tmp_path, "STD")
    assert run.returncode == 0, run.stderr


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("pic", PICS)
@pytest.mark.parametrize("op", ["ADD 1 TO S", "SUBTRACT 1 FROM S", "MULTIPLY 2 BY S", "DIVIDE 2 INTO S"])
def test_a_p_scaled_non_digit_receiver_is_refused_by_name(pic, op, tmp_path):
    """The receiver of ADD / SUBTRACT / MULTIPLY / DIVIDE is read by cobc too (#4889): a P item is refused as any."""
    pytest.importorskip("tree_sitter_language_pack")
    data = b"1!" if pic.startswith(("PIC S", "PIC SV")) else b"1A"
    run = _det(_pprogram(pic, op, data), tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr, run.stderr
    assert "receiver is a zoned item holding a non-digit is not modelled" in run.stderr, run.stderr


def _holes(src: str, work: Path) -> list[str]:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / "NDB.cbl").write_text(src)
    (work / "project").mkdir()
    r = P.translate(work / "NDB.cbl", [], "public class NdbService {\n}\n", "p", None, work / "project")
    return list(r.stats["holes"])


@pytest.mark.parametrize("pic", PICS)
@pytest.mark.parametrize("data", [b"12", b"1A", b"  "])
@pytest.mark.parametrize(
    ("op", "hole"),
    [("DISPLAY '[' S ']'", "a P-scaled item's DISPLAY form (#4670)"),
     ("INITIALIZE N REPLACING NUMERIC BY S", "INITIALIZE REPLACING"),
     ("STRING S DELIMITED BY SIZE INTO X", "STRING sender S"),
     ("STRING 'a' DELIMITED BY S INTO X", "STRING sender S")],
)  # fmt: skip
def test_a_p_scaled_display_initialize_and_string_are_refused_by_name(pic, data, op, hole, tmp_path):
    """DISPLAY of a P-scaled item (cobc prints the P positions' zeros as digits, IBM the stored bytes) and a P-scaled
    INITIALIZE ... REPLACING sender are holes at translation, digit-only or not (#4996)."""
    pytest.importorskip("tree_sitter_language_pack")
    holes = _holes(_pprogram(pic, op, data), tmp_path)
    assert len(holes) == 1 and hole in holes[0], holes


@pytest.mark.parametrize("pic", ["PIC VPP99", "PIC SVPP99"])
@pytest.mark.parametrize("data", [b"12", b"1A"])
@pytest.mark.parametrize("target", ["X", "XB"])
def test_a_noninteger_p_scaled_item_moved_to_alphanumeric_is_refused_by_name(pic, data, target, tmp_path):
    """Enterprise COBOL 6.4 Language Reference Table 47: a numeric noninteger sending item to an alphanumeric or
    alphanumeric-edited receiver is an invalid MOVE (a left-P item has only decimal places); cobc warns and moves."""
    pytest.importorskip("tree_sitter_language_pack")
    src = _pprogram(pic, f"MOVE S TO {target}", data).replace(
        "       01 N PIC 9(4).", "       01 N PIC 9(4).\n       01 XB PIC XXBXX."
    )
    holes = _holes(src, tmp_path)
    assert len(holes) == 1 and "a noninteger numeric item" in holes[0] and "Table 47" in holes[0], holes


@pytest.mark.parametrize("op", ["MOVE V TO X", "STRING V DELIMITED BY SIZE INTO X"])
def test_a_noninteger_numeric_to_alphanumeric_or_string_is_refused_by_name_without_p_too(op, tmp_path):
    """The same two rules without a P (Table 47; STRING needs an integer): `PIC 9V99` is no sender of either."""
    pytest.importorskip("tree_sitter_language_pack")
    src = _pprogram("PIC 99PP", op, b"12").replace(
        "01 S REDEFINES R PIC 99PP.", "01 S REDEFINES R PIC 99PP.\n       01 V PIC 9V99."
    )
    holes = _holes(src, tmp_path)
    assert len(holes) == 1 and ("noninteger numeric item" in holes[0] or "STRING sender V" in holes[0]), holes


# #4996: what reads a P item as bytes or as a digit-only number. Each case is `pic|data|op`; the op's lines print
# through DSX / DUX / BX (the receivers' bytes) so no DISPLAY form of a signed number is in play.
BYTE_READS = {
    "strref": "STRING S(1:1) DELIMITED BY SIZE INTO X", "refmod": "MOVE S(1:1) TO X", "movex": "MOVE S TO X",
}  # fmt: skip
VALUE_READS = {
    "mulby": "MOVE 3 TO DS\n           MULTIPLY S BY DS", "mulgiv": "MULTIPLY 2 BY S GIVING DS",
    "divinto": "MOVE 900000 TO DS\n           DIVIDE S INTO DS", "divby": "MOVE 1000 TO DS\n           DIVIDE DS BY S GIVING DU",
    "add": "MOVE 3 TO DS\n           ADD S TO DS", "sub": "MOVE 50 TO DS\n           SUBTRACT S FROM DS",
    "comp": "COMPUTE DS = S + 1", "du": "MOVE S TO DU", "bn": "MOVE S TO BN",
    "gt": "IF S > 5 MOVE 'g' TO X ELSE MOVE 'l' TO X END-IF", "eq": "IF S = 0 MOVE 'z' TO X ELSE MOVE 'n' TO X END-IF",
}  # fmt: skip


def _pdata(pic: str, dirty: bool) -> list[bytes]:
    signed = pic.startswith(("PIC S", "PIC SV"))
    if not dirty:
        return [b"12", b"07", b"1J"] if signed else [b"12", b"07"]
    # a byte read copies a non-digit as it is; a sign byte that is no overpunch ('!') cobc rewrites, even in a MOVE to
    # an alphanumeric item (a signed zoned item of any shape, not P-specific: a sibling gap of #4996)
    return [b"1A", b"  ", b"0J"] if signed else [b"1A", b"  "]


# a left-P item MOVEd to a binary one makes cobc 3.1.2 hang even digit-only: not measurable, so not a case
P_CASES = (
    [(pic, d, op) for pic in PICS for d in _pdata(pic, False) for op in VALUE_READS if not (op == "bn" and "VPP" in pic)]
    + [(pic, d, op) for pic in PICS for d in _pdata(pic, True) for op in BYTE_READS if not (op == "movex" and "VPP" in pic)]
)  # fmt: skip
P_EXPECTED = Path(__file__).with_name("nondigit_zoned_p_expected.txt")


def _vprogram(pic: str, op: str, data: bytes) -> str:
    body = (BYTE_READS | VALUE_READS)[op]
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION.", "       01 R PIC X(2).", f"       01 S REDEFINES R {pic}.",
             "       01 X PIC X(6) VALUE 'abcdef'.", "       01 DU PIC 9(7).", "       01 DUX REDEFINES DU PIC X(7).",
             "       01 DS PIC S9(7).", "       01 DSX REDEFINES DS PIC X(7).", "       01 BN PIC S9(9) COMP.",
             "       01 EW PIC -9(12).", "       PROCEDURE DIVISION.", f"           MOVE X'{data.hex().upper()}' TO R",
             f"           {body}", "           MOVE BN TO EW", "           DISPLAY '[' X '][' DUX '][' DSX '][' EW '][' R ']'",
             "           GOBACK.", ""]  # fmt: skip
    return "\n".join(lines)


def _pkey(case: tuple[str, bytes, str]) -> str:
    return f"{case[0]}|{case[1].hex()}|{case[2]}"


def _pexpected() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = ""
    for line in P_EXPECTED.read_text().split("\n"):
        if line.startswith("== "):
            key = line[3:]
            out[key] = []
        elif key and line != "== end":
            out[key].append(line)
    return out


def _pcobc(case: tuple[str, bytes, str], work: Path) -> str:
    (work / "ndb.cbl").write_text(_vprogram(case[0], case[2], case[1]))
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          f"cobc -x -std=ibm -fsign=EBCDIC {FLAGS['STD']} ndb.cbl -o ndb 2>&1 && timeout 10 ./ndb"],
                         capture_output=True, check=False, timeout=120)  # fmt: skip
    text = run.stdout.decode("latin-1")
    assert run.returncode == 0, text
    return "".join(x for x in text.splitlines(keepends=True) if not x.startswith("ndb.cbl:"))  # cobc's warnings


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("case", P_CASES, ids=_pkey)
def test_p_scaled_reads_that_are_modelled_are_the_oracles(case, tmp_path):
    """#4996: a digit-only P item's value (every arithmetic, compare and MOVE read, TRUNC STD) and a P item's bytes
    through STRING / reference modification / MOVE to alphanumeric, digit-only or not, print what cobc printed."""
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_vprogram(case[0], case[2], case[1]), tmp_path, "STD")
    assert run.returncode == 0, run.stderr
    assert _esc(run.stdout) == _pexpected()[_pkey(case)]


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker (EQUIVALENCE_E2E=1)")  # fmt: skip
@pytest.mark.parametrize("case", P_CASES[::7], ids=_pkey)
def test_the_p_expected_lines_are_cobcs(case, tmp_path):
    assert _esc(_pcobc(case, tmp_path)) == _pexpected()[_pkey(case)]


# ---------------------------------------------------------------------------------------------------------------
# #5032: siblings of #4996. A numeric item that is not a plain integer (or holds a bad sign byte) read by a
# non-arithmetic statement: MOVE to a national receiver, UNSTRING operands, a bad sign byte MOVEd to alphanumeric.
# ---------------------------------------------------------------------------------------------------------------
def _sprogram(decls: str, op: str, data: bytes = b"12") -> str:
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION.", "       01 R PIC X(4).", *[f"       {x}" for x in decls.split("\n")],
             "       01 X PIC X(8).", "       01 Y PIC X(8).", "       01 CT PIC 9(4).", "       01 PT PIC 9(4).",
             "       PROCEDURE DIVISION.", f"           MOVE X'{data.hex().upper()}' TO R", f"           {op}",
             "           GOBACK.", ""]  # fmt: skip
    return "\n".join(lines)


@pytest.mark.parametrize("pic", ["PIC 9V99", "PIC S9V99", "PIC VPP99", "PIC SVPP99", "PIC 99PP", "PIC 9(3)"])
@pytest.mark.parametrize("receiver", ["PIC N(4)", "PIC G(4)", "PIC X(4) USAGE NATIONAL", "PIC N(4) USAGE NATIONAL",
                                      "PIC X(4) USAGE DISPLAY-1", "PIC N(2)BN(2)"])  # fmt: skip
def test_a_move_to_a_national_receiver_is_refused_by_name_whatever_the_sender(pic, receiver, tmp_path):
    """Table 47 makes a noninteger numeric to NATIONAL invalid; the translator refuses every national item at the
    source (#4462 / #4664), so no sender shape reaches a national receiver (the integer ones included)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.layout import LayoutError

    src = _sprogram(f"01 V {pic}.\n01 NR {receiver}.", "MOVE V TO NR")
    (tmp_path / "NDB.cbl").write_text(src)
    (tmp_path / "project").mkdir()
    with pytest.raises(LayoutError, match="national / DBCS"):
        P.translate(tmp_path / "NDB.cbl", [], "public class NdbService {\n}\n", "p", None, tmp_path / "project")


UNSTRING_BAD = [  # (declarations, operation, what the hole names)
    ("01 V PIC 9(4).", "UNSTRING V DELIMITED BY ',' INTO X", "sending item V"),
    ("01 V PIC 9V99.", "UNSTRING V DELIMITED BY ',' INTO X", "sending item V"),
    ("01 V PIC 99PP.", "UNSTRING V DELIMITED BY ',' INTO X", "sending item V"),
    ("01 V PIC 9(2).", "UNSTRING R DELIMITED BY V INTO X", "DELIMITED BY item V"),
    ("01 V PIC 9V9.", "UNSTRING R DELIMITED BY ALL V INTO X", "DELIMITED BY item V"),
    ("01 V PIC 9V99.", "UNSTRING R DELIMITED BY ',' INTO V", "INTO item V"),
    ("01 V PIC 99PP.", "UNSTRING R DELIMITED BY ',' INTO V", "INTO item V"),
    ("01 V PIC SVPP99.", "UNSTRING R DELIMITED BY ',' INTO X COUNT IN V", "COUNT IN item V"),
    ("01 V PIC 9V9.", "UNSTRING R DELIMITED BY ',' INTO X WITH POINTER V", "POINTER item V"),
    ("01 V PIC 99PP.", "UNSTRING R DELIMITED BY ',' INTO X TALLYING IN V", "TALLYING item V"),
]  # fmt: skip
UNSTRING_GOOD = [
    ("01 V PIC 9(4).", "UNSTRING R DELIMITED BY ',' INTO V"),
    ("01 V PIC 9(4).", "UNSTRING R DELIMITED BY ',' INTO X COUNT IN V"),
    ("01 V PIC 9(4).", "UNSTRING R DELIMITED BY ',' INTO X WITH POINTER V"),
    ("01 V PIC 9(4).", "UNSTRING R DELIMITED BY ',' INTO X TALLYING IN V"),
    ("01 V PIC 99PP.", "UNSTRING V(1:2) DELIMITED BY ',' INTO X"),
    ("01 V PIC 9V99.", "UNSTRING R DELIMITED BY V(1:1) INTO X"),
]  # fmt: skip


@pytest.mark.parametrize(("decls", "op", "hole"), UNSTRING_BAD)
def test_an_unstring_numeric_operand_that_ibm_rejects_is_refused_by_name(decls, op, hole, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    holes = _holes(_sprogram(decls, op), tmp_path)
    assert len(holes) == 1 and f"UNSTRING {hole}" in holes[0] and "C11" in holes[0], holes


@pytest.mark.parametrize(("decls", "op", "ibm"), [
    ("01 V PIC 99PP.", "UNSTRING R DELIMITED BY ',' INTO V", True),
    ("01 V PIC 9V99.", "UNSTRING R DELIMITED BY ',' INTO V", False),
    ("01 V PIC 9(4).", "UNSTRING V DELIMITED BY ',' INTO X", True),
    ("01 V PIC 9V9.", "UNSTRING R DELIMITED BY ',' INTO X WITH POINTER V", True),
])  # fmt: skip
def test_an_unstring_refusal_names_whose_rule_it_is(decls, op, ibm, tmp_path):
    """A P in an INTO item, a non-integer COUNT / POINTER / TALLYING item and a numeric sender are IBM's rules (the
    Language Reference, UNSTRING, p. 465-466); a decimal INTO item is the port's conservative choice and must not be
    called an IBM compile error."""
    pytest.importorskip("tree_sitter_language_pack")
    (hole,) = _holes(_sprogram(decls, op), tmp_path)
    assert ("compile error in Enterprise COBOL" in hole) == ibm, hole


@pytest.mark.parametrize(("decls", "op"), UNSTRING_GOOD)
def test_an_unstring_integer_receiver_or_reference_modified_operand_is_translated(decls, op, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    assert _holes(_sprogram(decls, op), tmp_path) == []


SIGN_CASES = [  # (PICTURE, bytes, refused)
    *[("PIC S9(4)", d, bad) for d, bad in [(b"123!", True), (b"123\xff", True), (b"123x", True), (b"1234", False),
                                         (b"123}", False), (b"123J", False), (b"123 ", False), (b"!123", False)]],
    *[("PIC S9(4) SIGN LEADING", d, bad) for d, bad in [(b"!123", True), (b"\xff123", True), (b"1234", False),
                                                       (b"}123", False), (b"{123", False), (b" 123", False)]],
    *[("PIC S9(4) SIGN TRAILING SEPARATE", d, bad) for d, bad in [(b"1234!", True), (b"1234\xff", True),
                                                                 (b"1234+", False), (b"1234-", False)]],
    *[("PIC S9(4) SIGN LEADING SEPARATE", d, bad) for d, bad in [(b"!1234", True), (b"+1234", False),
                                                                (b"-1234", False)]],
]  # fmt: skip


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("target", ["X", "XB"])
@pytest.mark.parametrize(("pic", "data", "bad"), SIGN_CASES)
def test_a_bad_sign_byte_moved_to_alphanumeric_is_refused_by_name_and_a_good_one_is_not(
    pic, data, bad, target, tmp_path
):
    """IBM defines no result for a sign byte that is no sign (C11, undefined data), and cobc rewrites it to a digit:
    refused at run time; a digit, an overpunch, a space and a separate + / - are moved as ever. Only the sign
    position counts (a `!` in a digit position of a signed item is the unsigned rule's, not this one)."""
    pytest.importorskip("tree_sitter_language_pack")
    src = _sprogram(f"01 S REDEFINES R {pic}.\n01 XB PIC X(8) JUSTIFIED RIGHT.", f"MOVE S TO {target}", data)
    src = src.replace("01 R PIC X(4).", f"01 R PIC X({len(data)}).")
    run = _det(src, tmp_path, "STD")
    if bad:
        assert run.returncode != 0 and "register C11" in run.stderr and "sign byte" in run.stderr, run.stderr
    else:
        assert run.returncode == 0, run.stderr


if __name__ == "__main__":  # rewrite nondigit_zoned_expected.txt (and the receiver file) from cobc
    import tempfile

    parts = []
    for k in KINDS:
        for t in ("STD", "BIN"):
            with tempfile.TemporaryDirectory() as d:
                parts += [f"== {k} {t}", *_esc(_cobc(k, t, Path(d))), "== end"]
    EXPECTED.write_text("\n".join(parts) + "\n")
    parts = []
    for k in KINDS:
        for t in ("STD", "BIN"):
            with tempfile.TemporaryDirectory() as d:
                parts += [f"== {k} {t}", *_esc(_rcobc(k, t, Path(d))), "== end"]
    RECEIVER_EXPECTED.write_text("\n".join(parts) + "\n")
    parts = []
    for c in P_CASES:
        with tempfile.TemporaryDirectory() as d:
            parts += [f"== {_pkey(c)}", *_esc(_pcobc(c, Path(d))), "== end"]
    P_EXPECTED.write_text("\n".join(parts) + "\n")


# ---------------------------------------------------------------------------------------------------------------
# #4692: the PERFORM VARYING variable and the SET x UP / DOWN BY target are read before they store, as the receiver of
# ADD is: a zoned one holding a non-digit is refused by name (Cobol.receiverNum, register C11); a digit-only one steps.
# ---------------------------------------------------------------------------------------------------------------
VARYING_OP = "PERFORM VARYING V FROM 1 BY 1 UNTIL V > 2\n               CONTINUE END-PERFORM"


def _step_program(op: str, start: bytes) -> str:
    return "\n".join(["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. NDB.", "       DATA DIVISION.",
                      "       WORKING-STORAGE SECTION.", "       01 R PIC X(4).", "       01 V REDEFINES R PIC 9(4).",
                      "       PROCEDURE DIVISION.", f"           MOVE X'{start.hex().upper()}' TO R", f"           {op}",
                      "           DISPLAY 'R=' R", "           GOBACK.", ""])  # fmt: skip


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_non_digit_varying_variable_is_only_read_after_the_from_overwrites_it(tmp_path):
    """FROM stores before the first step reads, so spaces before the loop never reach the step: translated, 0003."""
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(_step_program(VARYING_OP, b"    "), tmp_path, "STD")
    assert run.returncode == 0, run.stderr
    assert "R=0003" in run.stdout.replace("\r", ""), run.stdout


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_varying_step_that_meets_a_non_digit_is_refused_by_name(tmp_path):
    """The loop body blanks the variable, so the next step reads spaces."""
    pytest.importorskip("tree_sitter_language_pack")
    op = "PERFORM VARYING V FROM 1 BY 1 UNTIL V > 2\n               MOVE SPACES TO R END-PERFORM"
    run = _det(_step_program(op, b"0000"), tmp_path, "STD")
    assert run.returncode != 0 and "register C11" in run.stderr, run.stderr
    assert "receiver is a zoned item holding a non-digit is not modelled" in run.stderr, run.stderr


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_a_digit_only_varying_step_counts_as_ever(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    run = _det(
        _step_program("PERFORM VARYING V FROM 1 BY 2 UNTIL V > 4\n               CONTINUE END-PERFORM", b"0000"),
        tmp_path,
        "STD",
    )
    assert run.returncode == 0, run.stderr
    assert "R=0005" in run.stdout.replace("\r", ""), run.stdout
