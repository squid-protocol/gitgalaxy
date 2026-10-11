"""Condition holes found proving the parser work of #4674 (#4681), GnuCOBOL 3.1.2 `-std=ibm` as the oracle.

1. `D0 + 1 > Q3` and 2. `S3 NOT < 3 + B0 * - D0`: arithmetic compared against an item of another scale -- the
   OSVS intermediate truncation (#4287) and the zero-divisor work (#4655) fixed both; these pin them end to end.
3. `A = 'B' OR NOT = 'C'`: an abbreviated combined relation whose omitted subject is followed by `NOT =` -- the
   grammar refused it, and with it the whole PROCEDURE DIVISION.

Needs EQUIVALENCE_E2E=1, Docker and a JDK 17 (the translator extra for tree-sitter)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CONDS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 S3 PIC S9(4)V999 VALUE -5.125.
       01 B0 PIC 9(4) COMP VALUE 579.
       01 D0 PIC 9(3) VALUE 7.
       01 Q3 PIC 9V999 VALUE 3.125.
       01 A  PIC X VALUE 'B'.
       PROCEDURE DIVISION.
           IF D0 + 1 > Q3
               DISPLAY 'H1A T'
           ELSE
               DISPLAY 'H1A F'
           END-IF
           IF D0 + 0 > Q3
               DISPLAY 'H1B T'
           ELSE
               DISPLAY 'H1B F'
           END-IF
           IF D0 + 1 < Q3
               DISPLAY 'H1C T'
           ELSE
               DISPLAY 'H1C F'
           END-IF
           IF S3 NOT < 3 + B0 * - D0
               DISPLAY 'H2A T'
           ELSE
               DISPLAY 'H2A F'
           END-IF
           IF S3 < 3 + B0 * - D0
               DISPLAY 'H2B T'
           ELSE
               DISPLAY 'H2B F'
           END-IF
           IF A = 'B' OR NOT = 'C'
               DISPLAY 'H3A T'
           ELSE
               DISPLAY 'H3A F'
           END-IF
           IF A = 'C' OR NOT = 'C'
               DISPLAY 'H3B T'
           ELSE
               DISPLAY 'H3B F'
           END-IF
           IF A = 'B' AND NOT = 'C'
               DISPLAY 'H3C T'
           ELSE
               DISPLAY 'H3C F'
           END-IF
           IF A NOT = 'C' AND NOT = 'B'
               DISPLAY 'H3D T'
           ELSE
               DISPLAY 'H3D F'
           END-IF
           STOP RUN.
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed"])
def test_the_condition_holes_agree_with_the_oracle(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(PROGRAM, cob)
    got = T._java_run("conds", PROGRAM, tmp_path, mode != "bytes")
    assert got == want, f"java {got!r} != cobol {want!r}"
    shown = dict(line.rsplit(" ", 1) for line in want.splitlines())
    # measured on the oracle: the branch cobc takes
    assert shown["H1A"] == "F" and shown["H1B"] == "F" and shown["H1C"] == "T"
    assert shown["H2A"] == "F" and shown["H2B"] == "T"
    assert shown["H3A"] == "T" and shown["H3B"] == "T" and shown["H3C"] == "T" and shown["H3D"] == "F"


# #4682: a NOT split from its operator by a line break, at every boundary and before every operator form
BREAKS = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. BREAKS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 D0 PIC 9(3) VALUE 7.
       PROCEDURE DIVISION.
           IF D0 NOT
               < 3
               DISPLAY 'B1 T'
           ELSE
               DISPLAY 'B1 F'
           END-IF
           IF D0 NOT
               LESS
               THAN 3
               DISPLAY 'B2 T'
           ELSE
               DISPLAY 'B2 F'
           END-IF
           IF D0 NOT
               <= 7
               DISPLAY 'B3 T'
           ELSE
               DISPLAY 'B3 F'
           END-IF
           IF D0 NOT >=
               7
               DISPLAY 'B4 T'
           ELSE
               DISPLAY 'B4 F'
           END-IF
           IF D0 NOT GREATER THAN OR
               EQUAL TO 8
               DISPLAY 'B5 T'
           ELSE
               DISPLAY 'B5 F'
           END-IF
           IF D0 > 1 AND NOT
               EQUAL TO 7
               DISPLAY 'B6 T'
           ELSE
               DISPLAY 'B6 F'
           END-IF
           IF D0 > 1 AND
               NOT
               < 5
               DISPLAY 'B7 T'
           ELSE
               DISPLAY 'B7 F'
           END-IF
           IF D0 > 1 AND
               GREATER THAN OR
               EQUAL 7
               DISPLAY 'B8 T'
           ELSE
               DISPLAY 'B8 F'
           END-IF
           IF D0 NOT NUMERIC
               DISPLAY 'B9 T'
           ELSE
               DISPLAY 'B9 F'
           END-IF
           IF D0 NOT
               POSITIVE
               DISPLAY 'B10 T'
           ELSE
               DISPLAY 'B10 F'
           END-IF
           EVALUATE TRUE
               WHEN D0 NOT
                   > 7
                   DISPLAY 'B11 T'
               WHEN OTHER
                   DISPLAY 'B11 F'
           END-EVALUATE
           PERFORM UNTIL D0 NOT
               < 9
               ADD 1 TO D0
           END-PERFORM
           DISPLAY 'B12 ' D0
           STOP RUN.
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed"])
def test_not_split_by_a_line_break_agrees_with_the_oracle(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(BREAKS, cob)
    got = T._java_run("breaks", BREAKS, tmp_path, mode != "bytes")
    assert got == want, f"java {got!r} != cobol {want!r}"
    shown = dict(line.rsplit(" ", 1) for line in want.splitlines())
    # D0 is 7: measured on the oracle, the branch cobc takes
    assert shown["B1"] == "T" and shown["B2"] == "T" and shown["B3"] == "F" and shown["B4"] == "F"
    assert shown["B5"] == "T" and shown["B6"] == "F" and shown["B7"] == "T" and shown["B8"] == "T"


# #4874: a floating `*>` comment inside conditions (fixed format), and `*>` inside a literal (data, not a comment)
COMMENTS = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CMTS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 D0 PIC 9(3) VALUE 7.
       01 A  PIC X(5) VALUE '*>'.
       PROCEDURE DIVISION.
           IF D0 < 3 *> hi
               DISPLAY 'C1 T'
           ELSE
               DISPLAY 'C1 F'
           END-IF
           IF D0 NOT *> c
               < 3
               DISPLAY 'C2 T'
           ELSE
               DISPLAY 'C2 F'
           END-IF
           IF D0 > 1 AND *> c
               < 9
               DISPLAY 'C3 T'
           ELSE
               DISPLAY 'C3 F'
           END-IF
           EVALUATE TRUE
               WHEN D0 NOT *> c
                   > 7 *> d
                   DISPLAY 'C4 T'
               WHEN OTHER
                   DISPLAY 'C4 F'
           END-EVALUATE
           PERFORM UNTIL D0 NOT *> c
               < 9 *> d
               ADD 1 TO D0
           END-PERFORM
           DISPLAY 'C5 ' D0
           IF A(1:2) = '*>' *> a literal, then a comment
               DISPLAY 'C6 *> T'
           END-IF
           STOP RUN.
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed"])
def test_a_floating_comment_in_a_condition_agrees_with_the_oracle(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_programs as T

    if T._java() is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(COMMENTS, cob)
    got = T._java_run("cmts", COMMENTS, tmp_path, mode != "bytes")
    assert got == want, f"java {got!r} != cobol {want!r}"
    assert "C6 *> T" in want  # the literal kept its `*>`
