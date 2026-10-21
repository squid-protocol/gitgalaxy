"""#5648: a COPY statement spread over lines, and EXEC SQL INCLUDE read as a COPY, live in core.cobol_preprocessor."""

from __future__ import annotations

from gitgalaxy.core.cobol_preprocessor import gather_copy, join_copy_alone, sql_include_as_copy, statement_end
from gitgalaxy.tools.cobol_to_java.det import source as SRC


def test_join_copy_alone():
    assert join_copy_alone(["    COPY", "      UPDCTL."], 0) == "    COPY UPDCTL."
    assert join_copy_alone(["    COPY", "      UPDCTL."], 1) is None
    assert join_copy_alone(["    COPY"], 0) is None  # no next line
    assert join_copy_alone(["    MOVE 'COPY"], 0) is None  # inside a literal
    assert join_copy_alone(["    COPY X."], 0) is None


def test_gather_copy_runs_to_the_period_and_not_past_it():
    texts = ["COPY A REPLACING ==X.Y==", "  BY ==Z==", "  .", "01 B."]
    stmt, j = gather_copy(texts, 0, 0)
    assert j == 2 and statement_end(stmt, 0) == len(stmt)
    assert gather_copy(["COPY A."], 0, 0) == ("COPY A.", 0)
    assert gather_copy(["COPY A", "  REPLACING"], 0, 0)[1] == 1  # never ends: all the lines, no overrun


def test_sql_include_as_copy_one_line_and_several():
    assert sql_include_as_copy(["EXEC SQL INCLUDE SQLCA END-EXEC."], 0) == ("COPY SQLCA.", 0)
    assert sql_include_as_copy(["EXEC SQL", "  INCLUDE DCLCUST", "END-EXEC."], 0) == ("COPY DCLCUST.", 2)
    assert sql_include_as_copy(["EXEC SQL SELECT 1 END-EXEC."], 0) is None
    assert sql_include_as_copy(["MOVE A TO B."], 0) is None


def _expand(tmp_path, fixed):
    (tmp_path / "A.cpy").write_text("       01  A-REC PIC X.\n")
    rows = ["       COPY", "         A.", "       EXEC SQL INCLUDE A END-EXEC.", "       01  C. COPY A."]
    if not fixed:
        rows = [r.strip() for r in rows]
        rows.insert(0, "       >>SOURCE FORMAT FREE")
    p = tmp_path / "P.cbl"
    p.write_text("\n".join(rows) + "\n")
    return [ln.text.strip() for ln in SRC.expand(SRC.logical_lines(p.read_text().splitlines(), str(p)), [tmp_path])]


def test_translator_expands_every_spelling_fixed_and_free(tmp_path):
    for fixed in (True, False):
        out = _expand(tmp_path, fixed)
        assert out.count("01  A-REC PIC X.") == 3, (fixed, out)
        assert "01  C." in out
