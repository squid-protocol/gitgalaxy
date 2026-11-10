"""#8121: a PROCEDURE DIVISION COPY member that holds EXEC CICS / EXEC SQL is read in before the precompile (cobc
refuses a bare EXEC inside a COPY member); a data COPY or a member without EXEC is left to the COPY pass."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       COPY WSDATA.\n"
    "       PROCEDURE DIVISION.\n"
    "           MOVE 1 TO X.\n"
    "       COPY ERRPD.\n"
    "       COPY PLAIN.\n"
    "      * COPY ERRPD.\n"
)


def _src(tmp_path: Path) -> Path:
    (tmp_path / "ERRPD.cpy").write_text(
        "       WRITE-IT.\n           EXEC CICS ASKTIME END-EXEC.\n", encoding="latin-1"
    )
    (tmp_path / "PLAIN.cpy").write_text("       P-1.\n           MOVE 2 TO X.\n", encoding="latin-1")
    (tmp_path / "WSDATA.cpy").write_text(
        "       01 X PIC 9.\n           EXEC SQL DECLARE END-EXEC.\n", encoding="latin-1"
    )
    return tmp_path


def test_exec_member_in_procedure_division_is_inlined(tmp_path):
    out = ec.inline_exec_copies(PROGRAM, _src(tmp_path))
    assert "EXEC CICS ASKTIME END-EXEC." in out
    assert "COPY ERRPD." not in out.replace("      * COPY ERRPD.", "")


def test_data_division_copy_and_plain_member_and_comment_are_untouched(tmp_path):
    out = ec.inline_exec_copies(PROGRAM, _src(tmp_path))
    assert "       COPY WSDATA.\n" in out
    assert "       COPY PLAIN.\n" in out
    assert "      * COPY ERRPD.\n" in out


def test_missing_member_is_left_alone(tmp_path):
    assert "COPY ERRPD." in ec.inline_exec_copies(PROGRAM, tmp_path)
