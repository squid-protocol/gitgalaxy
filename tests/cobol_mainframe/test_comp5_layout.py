"""#4751: a 1- or 2-digit COMP-5 item -- one byte in GnuCOBOL, a halfword on z/OS (oracle_assumptions.md C16).

IBM: binary items (COMP, COMP-4, BINARY, COMP-5) of 1 to 4 digits occupy a halfword, 5 to 9 a fullword, 10 to 18 a
doubleword (Enterprise COBOL for z/OS Language Reference, USAGE clause, "Computational items"). GnuCOBOL 3.1.2 under
`-std=ibm` (binary-size 2-4-8) lays out COMP / COMP-4 / BINARY so, but a COMP-5 of 1 or 2 digits (its PICTURE's 9s) in
one byte whatever -fbinary-size says. The det layout follows IBM; the oracle refuses such a program by name.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_common as common  # noqa: E402

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 G.
          05 A2 PIC S9(2) COMP-5.
          05 B2 PIC S9(2) COMP.
          05 A4 PIC S9(4) COMP-5.
          05 T  PIC X.
       PROCEDURE DIVISION.
           DISPLAY LENGTH OF A2 ' ' LENGTH OF B2 ' ' LENGTH OF G.
           MOVE 99999 TO A2.
           DISPLAY A2.
           GOBACK.
"""


def _src(*data: str) -> str:
    head = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
    return head + "".join(f"       {d}\n" for d in data)


@pytest.mark.parametrize(
    "data",
    [
        ["01 A PIC S9(2) COMP-5."],
        ["01 A PIC 9 COMP-5."],
        ["01 A PIC 99 USAGE IS COMPUTATIONAL-5 VALUE 7."],
        ["01 A COMP-5 PIC S9V9."],
        ["01 G USAGE COMP-5.", "   05 X PIC S9(4).", "   05 Y PIC S99."],
        ["01 A PIC 9PP COMP-5."],  # GnuCOBOL counts the 9s only: one byte
    ],
)
def test_a_one_byte_comp5_is_found(data):
    assert common.one_byte_comp5(_src(*data))


@pytest.mark.parametrize(
    "data",
    [
        ["01 A PIC S9(3) COMP-5."],
        ["01 A PIC S9(05) VALUE +4 COMP-5."],  # CardDemo IMSFUNCS.cpy's PARMCOUNT
        ["01 A PIC S99 COMP.", "01 B PIC 9 BINARY.", "01 C PIC S9 COMP-4."],  # halfwords under -std=ibm
        ["01 G USAGE COMP-5.", "   05 X PIC S9(4).", "01 H.", "   05 Y PIC S99."],  # the group's usage ends
        ["      *01 A PIC S99 COMP-5.", "01 B PIC X(2)."],
    ],
)
def test_a_halfword_or_wider_is_not(data):
    assert common.one_byte_comp5(_src(*data)) == []


def test_the_oracle_refuses_the_program_by_name(tmp_path):
    (tmp_path / "PROGRAM.cbl").write_text(_src("01 A PIC S9(4) COMP-5."))
    (tmp_path / "ggsql.c").write_text("short x; /* 05 A PIC S99 COMP-5. */\n")
    common.comp5_layout_guard(tmp_path)  # a halfword, and a C file is not COBOL
    (tmp_path / "CPY").write_text("       01 R.\n          05 F PIC S99 COMP-5.\n")
    with pytest.raises(common.UnsupportedOption, match=r"CPY: `05 F PIC S99 COMP-5`.*C16"):
        common.comp5_layout_guard(tmp_path)


def test_the_det_layout_is_ibms(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det.layout import records

    (tmp_path / "P.cbl").write_text(PROGRAM)
    g = next(r for r in records(tmp_path / "P.cbl", []) if r.name == "G")
    sizes = {c.name: (c.offset, c.size) for c in g.children}
    assert sizes == {"A2": (0, 2), "B2": (2, 2), "A4": (4, 2), "T": (6, 1)} and g.size == 7


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and the GnuCOBOL image (EQUIVALENCE_E2E=1)")  # fmt: skip
@pytest.mark.parametrize("flags", ["", "-fbinary-size=2-4-8", "-fbinary-truncate"])
def test_gnucobol_lays_it_out_in_one_byte(tmp_path, flags):
    """What the guard is for, measured: if a new image lays it out in a halfword, drop the guard (and C16)."""
    (tmp_path / "prog.cbl").write_text(PROGRAM)
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", common.IMAGE, "sh", "-c",  # noqa: S607
                          f"cobc -x -std=ibm -fsign=EBCDIC {flags} prog.cbl -o prog 2>/dev/null && ./prog"],
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert run.stdout.split() == ["1", "2", "6", "-097"], run.stdout + run.stderr  # IBM: 2 2 7, -31073
