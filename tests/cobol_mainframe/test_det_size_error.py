"""Size errors in the det port (#4655, oracle_assumptions C14): a zero divisor, 0 ** 0, an exponent without a finite
result and a receiver too small, with and without ON SIZE ERROR, as the oracle (GnuCOBOL 3.1.2 `-std=ibm`) does them.

A zero divisor makes libcob's NaN intermediate: the receivers keep their values (every receiver of the statement,
each receiver of DIVIDE ... INTO), the REMAINDER too; cob_decimal_align turns a NaN into 0, a function's argument
divided by zero is 0, and the size error is raised either way. The codegen tests need no Docker; the end-to-end test
runs one program through GnuCOBOL and the det port (EQUIVALENCE_E2E=1, Docker and a JDK 17)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import gen as G  # noqa: E402


def test_only_a_division_or_an_exponent_can_be_nan():
    assert G._may_nan(E.parse_arith("A / B + 1"))
    assert G._may_nan(E.parse_arith("- (A ** B)"))
    assert not G._may_nan(E.parse_arith("A * B - C"))
    # a function's value never is: cob_intr_binop gives 0 for a zero divisor
    assert not G._may_nan(E.parse_arith("FUNCTION ABS(A / B) + 1"))


def test_a_function_argument_still_raises_the_size_error():
    assert G._raises_size(E.parse_arith("FUNCTION ABS(A / B) + 1"))
    assert G._raises_size(E.parse_arith("A ** 2"))
    assert not G._raises_size(E.parse_arith("FUNCTION MOD(A, B)"))  # measured: MOD / REM by zero raise nothing
    assert not G._raises_size(E.parse_arith("A + B * C"))


def _tree(*body: str):
    from gitgalaxy.tools.cobol_to_java.det import source as SRC
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    rows = [
        "IDENTIFICATION DIVISION.",
        "PROGRAM-ID. PROG.",
        "DATA DIVISION.",
        "WORKING-STORAGE SECTION.",
        "01 A PIC 9.",
        "PROCEDURE DIVISION.",
        "P1.",
        *body,
        "    GOBACK.",
    ]
    return ST.parse(SRC.logical_lines(["       " + r for r in rows], "/x/PROG.cbl")).paragraphs[0].body


def test_a_phrase_binds_to_the_innermost_unterminated_statement():
    """#4676 (cobc): NOT ON SIZE ERROR after a nested, unterminated COMPUTE is the nested one's; an END-COMPUTE closes
    the innermost COMPUTE, so what follows it stays in the nested statement's phrase."""
    pytest.importorskip("tree_sitter_language_pack")
    outer = _tree(
        "COMPUTE A = 1",
        "  ON SIZE ERROR COMPUTE A = A * A",
        "  NOT ON SIZE ERROR COMPUTE A = A + A",
        "END-COMPUTE",
        "DISPLAY A.",
    )[0]
    assert set(outer.phrases) == {"SIZE-ERROR"}
    inner = outer.phrases["SIZE-ERROR"][0]
    assert set(inner.phrases) == {"NOT-SIZE-ERROR"}
    # the END-COMPUTE closed the COMPUTE inside the inner NOT phrase; the DISPLAY after it is still in that phrase
    assert [x.kind for x in inner.phrases["NOT-SIZE-ERROR"]] == ["COMPUTE", "DISPLAY"]
    assert [x.kind for x in outer.phrases["SIZE-ERROR"]] == ["COMPUTE"]
    # terminated: the NOT phrase is the outer statement's again
    outer = _tree(
        "COMPUTE A = 1",
        "  ON SIZE ERROR COMPUTE A = A * A END-COMPUTE",
        "  NOT ON SIZE ERROR DISPLAY A",
        "END-COMPUTE.",
    )[0]
    assert set(outer.phrases) == {"SIZE-ERROR", "NOT-SIZE-ERROR"}
    assert not outer.phrases["SIZE-ERROR"][0].phrases


PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIZEERR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A  PIC 999V99 VALUE 50.
       01 Z0 PIC 9 VALUE 0.
       01 ZN PIC S9 VALUE 0.
       01 M1 PIC S9 VALUE -1.
       01 M2 PIC S9 VALUE -2.
       01 A59 PIC 99 VALUE 59.
       01 Q99 PIC 99 VALUE 0.
       01 R  PIC 999V99 VALUE 12.34.
       01 R2 PIC 999V99 VALUE 56.78.
       01 RM PIC 999V99 VALUE 9.99.
       01 RB PIC 9(4) COMP VALUE 77.
       01 RP PIC S9(5)V99 COMP-3 VALUE 11.
       01 RE PIC ZZ9.99 VALUE '  5.00'.
       01 W  PIC 9(5)V99.
       01 S  PIC 9(3) VALUE 123.
       01 T  PIC 9(3) VALUE 456.
       01 AN PIC S999V99 VALUE -50.
       01 B  PIC 9 VALUE 3.
       01 C  PIC 999 VALUE 300.
       01 ZZ PIC 9 VALUE 0.
       01 K  PIC 9 VALUE 0.
       01 Q  PIC 9 VALUE 0.
       01 R3 PIC 999V99 VALUE 2.
       01 F1 COMP-1 VALUE 5.
       01 F2 COMP-2 VALUE 7.
       01 FZ1 COMP-1 VALUE 0.
       01 FZ2 COMP-2 VALUE 0.
       01 G1 COMP-1 VALUE 1.5.
       01 G2 COMP-2 VALUE 2.5.
       01 E1 PIC -(5)9.99.
       01 E2 PIC -(5)9.99.
       PROCEDURE DIVISION.
           COMPUTE R = A / Z0
           DISPLAY 'C1 ' R
           COMPUTE R R2 = A / Z0
           DISPLAY 'C2 ' R ' ' R2
           COMPUTE R = A / Z0 + 1
           DISPLAY 'C3 ' R
           COMPUTE R = (A / Z0) * 0 + 7
           DISPLAY 'C4 ' R
           COMPUTE RB = A / Z0
           MOVE RB TO W
           DISPLAY 'C5 ' W
           COMPUTE RP = A / Z0
           MOVE RP TO W
           DISPLAY 'C6 ' W
           COMPUTE RE = A / Z0
           DISPLAY 'C7 ' RE
           DIVIDE Z0 INTO A GIVING R R2
           DISPLAY 'D1 ' R ' ' R2
           DIVIDE Z0 INTO R R2
           DISPLAY 'D2 ' R ' ' R2
           DIVIDE A BY Z0 GIVING R REMAINDER RM
           DISPLAY 'D3 ' R ' ' RM
           DIVIDE Z0 INTO R ROUNDED
           DISPLAY 'D4 ' R
           COMPUTE R = Z0 ** M1
           DISPLAY 'P1 ' R
           COMPUTE R = Z0 ** M2 + 3
           DISPLAY 'P2 ' R
           COMPUTE R = ZN ** 0
           DISPLAY 'P3 ' R
           COMPUTE R = 0 ** 0
           DISPLAY 'P4 ' R
           COMPUTE R = 123456
           DISPLAY 'O1 ' R
           COMPUTE R R2 = A * 100
           DISPLAY 'O2 ' R ' ' R2
           ADD 99999 TO R
           DISPLAY 'O3 ' R
           MULTIPLY 1000 BY R
           DISPLAY 'O4 ' R
           ADD S T GIVING R
           DISPLAY 'O5 ' R
           COMPUTE R = A / Z0
             ON SIZE ERROR DISPLAY 'SE1 Y ' R
             NOT ON SIZE ERROR DISPLAY 'SE1 N ' R
           END-COMPUTE
           DIVIDE Z0 INTO R R2
             ON SIZE ERROR DISPLAY 'SE2 Y ' R ' ' R2
           END-DIVIDE
           DIVIDE A BY Z0 GIVING R REMAINDER RM
             ON SIZE ERROR DISPLAY 'SE3 Y ' R ' ' RM
           END-DIVIDE
           COMPUTE R = Z0 ** M1
             ON SIZE ERROR DISPLAY 'SE4 Y ' R
             NOT ON SIZE ERROR DISPLAY 'SE4 N ' R
           END-COMPUTE
           MOVE 5 TO R
           COMPUTE R = 2 / 4
             ON SIZE ERROR DISPLAY 'SE5 Y ' R
             NOT ON SIZE ERROR DISPLAY 'SE5 N ' R
           END-COMPUTE
           IF A / Z0 = 0 DISPLAY 'I1 EQ0' ELSE DISPLAY 'I1 NE0'
           END-IF
           IF A / Z0 = A DISPLAY 'I2 EQA' ELSE DISPLAY 'I2 NEA'
           END-IF
           IF A / Z0 > 1000 DISPLAY 'I3 GT' ELSE DISPLAY 'I3 LE'
           END-IF
           DIVIDE 6 INTO A59 GIVING Q99 ROUNDED REMAINDER RM
           DISPLAY 'RR ' Q99 ' ' RM
           MOVE 12.34 TO R
           COMPUTE R = A / Z0 * C
           DISPLAY 'A1 ' R
           MOVE 12.34 TO R
           COMPUTE R = A / Z0 * C
             ON SIZE ERROR DISPLAY 'A2 Y ' R
             NOT ON SIZE ERROR DISPLAY 'A2 N ' R
           END-COMPUTE
           COMPUTE R = ZZ ** 0
             ON SIZE ERROR DISPLAY 'E1 Y ' R
             NOT ON SIZE ERROR DISPLAY 'E1 N ' R
           END-COMPUTE
           PERFORM VARYING K FROM 0 BY 1 UNTIL K > 2
             IF K = 0 MOVE 7 TO ZZ ELSE MOVE 0 TO ZZ END-IF
             COMPUTE R = FUNCTION ABS(A / ZZ)
             DISPLAY 'F' K ' ' R
           END-PERFORM
           COMPUTE R = FUNCTION ABS(A / Z0)
             ON SIZE ERROR DISPLAY 'F3 Y ' R
             NOT ON SIZE ERROR DISPLAY 'F3 N ' R
           END-COMPUTE
           COMPUTE R = (A / Z0) + (A / B)
           DISPLAY 'N1 ' R
           IF 0 = A / Z0 DISPLAY 'N2 EQ' ELSE DISPLAY 'N2 NE'.
           IF A / Z0 + 5 = 5 DISPLAY 'N3 EQ' ELSE DISPLAY 'N3 NE'.
           IF (A / Z0) - (A / Z0) = 0 DISPLAY 'N4 EQ'
             ELSE DISPLAY 'N4 NE'.
           MOVE 12.34 TO R
           COMPUTE R = Z0 / Z0
           DISPLAY 'Z1 ' R
           COMPUTE R = AN ** 0.5
             ON SIZE ERROR DISPLAY 'W1 Y ' R
             NOT ON SIZE ERROR DISPLAY 'W1 N ' R
           END-COMPUTE
           COMPUTE R = A ** 300.5
             ON SIZE ERROR DISPLAY 'W2 Y ' R
             NOT ON SIZE ERROR DISPLAY 'W2 N ' R
           END-COMPUTE
           COMPUTE R = FUNCTION MOD(A, Z0)
             ON SIZE ERROR DISPLAY 'M1 Y ' R
             NOT ON SIZE ERROR DISPLAY 'M1 N ' R
           END-COMPUTE
           MOVE 12.34 TO R
           COMPUTE R = FUNCTION REM(A, Z0)
             ON SIZE ERROR DISPLAY 'M2 Y ' R
             NOT ON SIZE ERROR DISPLAY 'M2 N ' R
           END-COMPUTE
           MOVE 9.99 TO RM
           DIVIDE 0.01 INTO A GIVING Q REMAINDER RM
           DISPLAY 'Q1 ' Q ' ' RM
           MOVE 9.99 TO RM
           DIVIDE 0.01 INTO A GIVING Q REMAINDER RM
             ON SIZE ERROR DISPLAY 'Q2 Y ' Q ' ' RM
           END-DIVIDE
           MOVE 12.34 TO R
           COMPUTE R = A / Z0
             ON SIZE ERROR
               COMPUTE R2 = A / B * C
               END-COMPUTE
             NOT ON SIZE ERROR
               COMPUTE R2 = A / B * 7
               END-COMPUTE
           END-COMPUTE
           DISPLAY 'B1 ' R ' ' R2
           COMPUTE G1 = F1 / FZ1
           MOVE G1 TO E1
           DISPLAY 'H1 ' E1
           COMPUTE G2 = F2 / Z0
           MOVE G2 TO E2
           DISPLAY 'H2 ' E2
           COMPUTE R = F2 / FZ2
           DISPLAY 'H3 ' R
           COMPUTE G1 = F1 / FZ1
             ON SIZE ERROR DISPLAY 'H4 Y'
             NOT ON SIZE ERROR DISPLAY 'H4 N'
           END-COMPUTE
           MOVE G1 TO E1
           DISPLAY 'H4v ' E1
           COMPUTE G2 = F2 / FZ2
             ON SIZE ERROR DISPLAY 'H5 Y'
             NOT ON SIZE ERROR DISPLAY 'H5 N'
           END-COMPUTE
           MOVE G2 TO E2
           DISPLAY 'H5v ' E2
           DIVIDE FZ2 INTO G2
           MOVE G2 TO E2
           DISPLAY 'H6 ' E2
           DIVIDE FZ1 INTO G1
             ON SIZE ERROR DISPLAY 'H7 Y'
             NOT ON SIZE ERROR DISPLAY 'H7 N'
           END-DIVIDE
           MOVE G1 TO E1
           DISPLAY 'H7v ' E1
           DIVIDE F2 BY FZ2 GIVING G2
             ON SIZE ERROR DISPLAY 'H8 Y'
           END-DIVIDE
           MOVE G2 TO E2
           DISPLAY 'H8v ' E2
           DIVIDE F2 BY FZ2 GIVING R
             ON SIZE ERROR DISPLAY 'H9 Y'
           END-DIVIDE
           DISPLAY 'H9v ' R
           COMPUTE G2 = F2 * 3
             ON SIZE ERROR DISPLAY 'HA Y'
             NOT ON SIZE ERROR DISPLAY 'HA N'
           END-COMPUTE
           MOVE 12.34 TO R
           COMPUTE R = F2 * 3000
             ON SIZE ERROR DISPLAY 'HB Y'
             NOT ON SIZE ERROR DISPLAY 'HB N'
           END-COMPUTE
           DISPLAY 'HBv ' R
           MOVE 12.34 TO R
           MOVE 1 TO R2
           COMPUTE R = A / Z0
             ON SIZE ERROR COMPUTE R2 = A / B * C
             NOT ON SIZE ERROR COMPUTE R2 = A / B * 7
           END-COMPUTE
           DISPLAY 'U1 ' R ' ' R2
           DISPLAY 'U1b'.
           MOVE 1 TO R2
           COMPUTE R = A / Z0
             ON SIZE ERROR COMPUTE R2 = A / B * C
               ON SIZE ERROR DISPLAY 'U2 in Y'
               NOT ON SIZE ERROR DISPLAY 'U2 in N'
             NOT ON SIZE ERROR COMPUTE R2 = A / B * 7
           END-COMPUTE
           DISPLAY 'U2 ' R ' ' R2
           DISPLAY 'U2b'.
           MOVE 1 TO R2
           COMPUTE R = A / Z0
             ON SIZE ERROR COMPUTE R2 = A / B * C
               ON SIZE ERROR DISPLAY 'U3 in Y'
               NOT ON SIZE ERROR DISPLAY 'U3 in N'
             END-COMPUTE
             NOT ON SIZE ERROR COMPUTE R2 = A / B * 7
           END-COMPUTE
           DISPLAY 'U3 ' R ' ' R2
           DISPLAY 'U3b'.
           MOVE 1 TO R2
           COMPUTE R = A / Z0
             ON SIZE ERROR
               IF B > 1
                 COMPUTE R2 = A / B * C
                 NOT ON SIZE ERROR DISPLAY 'U4 if N'
               END-IF
               DISPLAY 'U4 x'
             NOT ON SIZE ERROR DISPLAY 'U4 outer N'
           END-COMPUTE
           DISPLAY 'U4 ' R ' ' R2
           DISPLAY 'U4b'.
           MOVE 1 TO R2
           COMPUTE R = A / B
             ON SIZE ERROR DISPLAY 'U5 o Y'
             NOT ON SIZE ERROR
               COMPUTE R2 = A / Z0
                 ON SIZE ERROR DISPLAY 'U5 i Y'
               ADD 1 TO R3
                 NOT ON SIZE ERROR DISPLAY 'U5 a N'
             END-COMPUTE
           DISPLAY 'U5 ' R ' ' R2 ' ' R3
           DISPLAY 'U5b'.
           ADD 1 TO R
             ON SIZE ERROR DISPLAY 'U6 o Y'
             NOT ON SIZE ERROR
               MULTIPLY 2 BY R3
               SUBTRACT 1 FROM R3 ON SIZE ERROR DISPLAY 'U6 i Y'
               END-SUBTRACT
               ADD A TO R2 NOT ON SIZE ERROR DISPLAY 'U6 in N'
             END-ADD
           DISPLAY 'U6 ' R ' ' R2 ' ' R3
           DISPLAY 'U6b'.
           GOBACK.
"""

# what the oracle prints (measured 2026-10-07, GnuCOBOL 3.1.2 -std=ibm; R starts 12.34, R2 56.78, RM 9.99)
WANT = {
    "C1": "01234", "C2": "01234 05678", "C3": "01234", "C4": "01234", "C5": "0007700", "C6": "0001100",
    "C7": "  5.00", "D1": "01234 05678", "D2": "01234 05678", "D3": "01234 00999", "D4": "01234",
    "P1": "00000", "P2": "00300", "P3": "00100", "P4": "00100",
    "O1": "45600", "O2": "00000 00000", "O3": "99900", "O4": "00000", "O5": "57900",
    "SE1": "Y 57900", "SE2": "Y 57900 00000", "SE3": "Y 57900 00999", "SE4": "N 00000", "SE5": "N 00050",
    "I1": "EQ0", "I2": "NEA", "I3": "LE", "RR": "10 00500",
    "A1": "00000", "A2": "Y 00000", "E1": "Y 00100", "F0": "00714", "F1": "00000", "F2": "00000", "F3": "Y 00000",
    "N1": "01666", "N2": "NE", "N3": "NE", "N4": "EQ", "Z1": "01234", "W1": "Y 01234", "W2": "Y 01234",
    "M1": "N 00000", "M2": "N 00000", "Q1": "0 00000", "Q2": "Y 0 00000", "B1": "01234 99800",
    "H1": "     1.50", "H2": "     2.50", "H3": "01234", "H4": "Y", "H4v": "     1.50", "H5": "Y", "H5v": "     2.50",
    "H6": "     2.50", "H7": "Y", "H7v": "     1.50", "H8": "Y", "H8v": "     2.50", "H9": "Y", "H9v": "01234", "HA": "N",
    "HB": "Y", "HBv": "01234",
    "U2": "in Y", "U3": "in Y", "U4": "01234 00100", "U5": "01666 00100 00300", "U6": "01766 05100 00500",
}  # fmt: skip


def _java_ok() -> bool:
    import test_det_programs as T

    return T._java() is not None


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed"])
def test_size_errors_are_the_oracles(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_programs as T

    if not _java_ok():
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(PROGRAM, cob)
    got = T._java_run("sizeerr", PROGRAM, tmp_path, mode != "bytes")
    shown = dict(line.split(" ", 1) for line in want.splitlines() if " " in line and not line.startswith("prog.cbl"))
    for k, v in WANT.items():
        assert shown[k] == v, (k, shown[k])
    assert got.splitlines() == [x for x in want.splitlines() if not x.startswith("prog.cbl")]
