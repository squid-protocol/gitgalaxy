"""#4884: the CEEIGZCT stand-in (det/copy/CEEIGZCT.cpy) resolves only where the estate holds no member of its own, and
a literal that merely contains the words EXEC CICS is text, not an EXEC block (CBSA CRECUST's DISPLAYs)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402

PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. FCUSER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 FC.
          02 CONDITION-TOKEN-VALUE.
           COPY  CEEIGZCT.
             03 SEVERITY PIC S9(4) BINARY.
             03 MSG-NO PIC S9(4) BINARY.
             03 CASE-SEV-CTL PIC X.
             03 FACILITY-ID PIC XXX.
       PROCEDURE DIVISION.
       P1.
           IF NOT CEE000 OF FC
              DISPLAY 'EXEC CICS FETCH ANY failed. RESP='
           END-IF.
           EXEC CICS RETURN
           END-EXEC.
"""


def _lines(tmp_path, dirs):
    (tmp_path / "FCUSER.cbl").write_text(PROGRAM)
    return SRC.program_lines(tmp_path / "FCUSER.cbl", dirs)


def test_stand_in_resolves_where_the_estate_has_no_member(tmp_path):
    text = "\n".join(ln.text for ln in _lines(tmp_path, [SRC._SHIPPED_COPY]))
    assert "CEE000 VALUE X'0000000000000000'" in text
    assert "GitGalaxy-written, NOT IBM's member" in (SRC._SHIPPED_COPY / "CEEIGZCT.cpy").read_text()


def test_the_estates_own_member_wins_over_the_stand_in(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "CEEIGZCT.cpy").write_text("           88 CEE000 VALUE 'OWN'.\n")
    text = "\n".join(ln.text for ln in _lines(tmp_path, [lib, SRC._SHIPPED_COPY]))
    assert "VALUE 'OWN'" in text and "X'0000000000000000'" not in text


def test_a_literal_containing_exec_cics_is_not_an_exec_block(tmp_path):
    proc = S.parse(_lines(tmp_path, [SRC._SHIPPED_COPY]))
    assert repr(proc.paragraphs).count("GGEXEC") == 0 and [s.kind for p in proc.paragraphs for s in p.body] == [
        "IF",
        "EXEC",
    ]


def test_the_inventory_records_stand_in_use_only_where_the_stand_in_answered(tmp_path):
    """#5565: `stand_in_copybooks` names each stand-in member a program's COPY read from the shipped directory; an
    estate's own member of that name is not a stand-in use, and an estate with none has no such category."""
    from gitgalaxy.tools.readiness.inventory import scan_estate

    own, bare = tmp_path / "own", tmp_path / "bare"
    for d in (own, bare):
        d.mkdir()
    (bare / "FCUSER.cbl").write_text(PROGRAM)
    (own / "FCUSER.cbl").write_text(PROGRAM)
    (own / "CEEIGZCT.cpy").write_text("           03 CEE000 PIC X.\n")
    inv = scan_estate(bare, tmp_path / "db1")
    assert {k: sorted(v["programs"]) for k, v in inv["stand_in_copybooks"].items()} == {"CEEIGZCT": ["FCUSER.cbl"]}
    assert "stand_in_copybooks" not in scan_estate(own, tmp_path / "db2")
