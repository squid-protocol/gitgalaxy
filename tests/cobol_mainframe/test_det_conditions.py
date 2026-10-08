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
