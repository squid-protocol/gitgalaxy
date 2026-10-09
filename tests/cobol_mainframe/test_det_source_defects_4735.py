"""#4735: a defective source is refused or reported BY NAME, never repaired and never `no such item` / `SystemExit: 0`:
text past column 72 that cuts a host variable or loses a comma, a saved ISPF editor screen, an undeclared item or
paragraph. Fixture snippets only (the census programs -- NexusBank NEND-DAY, cobol-db2-cursor, refatorado ALTERAR --
are not needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.core.cobol_source_format import ispf_screen, ispf_screens  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

HEAD = ("IDENTIFICATION DIVISION.", "PROGRAM-ID. TW.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        "01  WS-MSG                PIC X(40) VALUE SPACES.")  # fmt: skip


def _row(code: str, tail: str = "", at: int = 72) -> str:
    """A fixed-form line: `code` from column 8, `tail` from column 73."""
    return ("       " + code).ljust(at) + tail


def _lines(*rows: str) -> list:
    return SRC.logical_lines(list(rows), "/x/NEND-DAY.cbl")


def test_a_host_variable_cut_at_column_72_is_a_named_source_defect():
    """NEND-DAY line 411: `... - :HV-SO-IM` ends in column 72, `PORTO,` is in columns 73-78."""
    rows = [_row(t) for t in HEAD] + [("       " + "EXEC SQL SELECT A WHERE B - :HV-SO-IM").rjust(72) + "PORTO,"]
    why = SRC.refusal(_lines(*rows))
    assert why == ("NEND-DAY.cbl:6: source defect: source text past column 72 (`PORTO,`) truncates `:HV-SO-IM`: "
                   "fixed-form COBOL reads columns 8-72 only")  # fmt: skip


def test_a_comma_lost_in_column_73_is_a_named_source_defect():
    """NEND-DAY lines 308, 309, 316: the separator comma sits in column 73."""
    rows = [_row(t) for t in HEAD] + [_row("    EXEC SQL SELECT A INTO :HV-A", ",")]
    why = SRC.refusal(_lines(*rows))
    assert why is not None and "source defect: source text past column 72 (`,`) is cut off after" in why


def test_a_defect_in_a_continued_line_is_named_too():
    rows = [_row(t) for t in HEAD] + [_row("    MOVE 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", ""),
                                      "      -    'BB' TO WS-MSG"]  # fmt: skip
    assert SRC.refusal(_lines(*rows)) is None  # a properly continued literal is read
    rows[-1] = rows[-1].ljust(72) + "(X)"
    assert "source defect: source text past column 72 (`(X)`)" in (SRC.refusal(_lines(*rows)) or "")


@pytest.mark.parametrize("tail", ["00000100", "COF00010", "NEND-DAY", "-", ".", "E", "*> note", ""])
def test_identification_area_tags_and_comments_past_column_72_lose_nothing(tail):
    rows = [_row(t, tail) for t in HEAD] + [_row("    MOVE 'A' TO WS-MSG.", tail)]
    assert SRC.refusal(_lines(*rows)) is None


def test_free_format_text_past_column_72_is_not_a_defect():
    rows = ["       >>SOURCE FORMAT FREE", *HEAD, "01  WS-LONG PIC X(10) VALUE 'A'" + " " * 60 + ", X."]
    assert SRC.refusal(_lines(*rows)) is None


def test_the_defect_reaches_the_layout_and_statement_parsers():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    rows = [_row(t) for t in HEAD] + [_row("PROCEDURE DIVISION."), _row("    MOVE A TO :HV-SO-IM", "PORTO,")]
    lines = _lines(*rows)
    with pytest.raises(L.LayoutError, match="source defect: source text past column 72"):
        L.parse(lines)
    with pytest.raises(E.ExprError, match="source defect: source text past column 72"):
        ST.parse(lines)


# ---- a saved ISPF editor screen ------------------------------------------------------------------------------------
ISPF = """\
 File  Edit  Edit_Settings  Menu  Utilities  Compilers  Test  Help
-------------------------------------------------------------------------------
EDIT       USER.COBOL(CURSOR) - 01.00                       Columns 00001 00072
Command ===>                                                  Scroll ===> CSR
****** ***************************** Top of Data ******************************
000001        IDENTIFICATION DIVISION.
000002        PROGRAM-ID. CURSOR.
****** **************************** Bottom of Data ****************************
"""


def test_an_ispf_screen_is_named_and_a_program_that_mentions_one_marker_is_not():
    assert ispf_screen(ISPF) == "menu bar, EDIT title, command line, data banner"
    real = "       IDENTIFICATION DIVISION.\n      * Command ===> is what the user types\n       PROGRAM-ID. P.\n"
    assert ispf_screen(real) is None
    assert ispf_screen("      * File Edit Edit_Settings Menu\n       PROGRAM-ID. P.\n") is None


def test_the_translator_refuses_an_ispf_screen_by_name(tmp_path):
    prog = tmp_path / "CURSOR.cbl"
    prog.write_text(ISPF, encoding="utf-8")
    with pytest.raises(SRC.NotCobol, match=r"CURSOR\.cbl: not a COBOL program: ISPF editor screen"):
        SRC.program_lines(prog, [])


def test_ispf_screens_lists_the_files_of_an_estate(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "CURSOR.cbl").write_text(ISPF, encoding="utf-8")
    (tmp_path / "OK.cbl").write_text("       PROGRAM-ID. OK.\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text(ISPF, encoding="utf-8")
    assert [n for n, _ in ispf_screens(tmp_path)] == ["sub/CURSOR.cbl"]
    assert [n for n, _ in ispf_screens(tmp_path / "OK.cbl")] == []


def test_the_refactor_controller_names_an_ispf_screen_instead_of_only_finding_nothing(tmp_path, capsys):
    from unittest.mock import patch

    from gitgalaxy import cobol_refractor_controller as ctl

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CURSOR.cbl").write_text(ISPF, encoding="utf-8")
    with patch("sys.argv", ["refract", str(repo)]), pytest.raises(SystemExit) as exc:
        ctl.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "No executable COBOL files found" in out
    assert "not a COBOL program: ISPF editor screen: CURSOR.cbl" in out


# ---- undeclared items and paragraphs -------------------------------------------------------------------------------
def _program(tmp_path, proc: list[str]) -> Path:
    src = tmp_path / "TW.cbl"
    src.write_text(
        "".join(f"       {t}\n" for t in (*HEAD, "PROCEDURE DIVISION.", "MAIN-PARA.", *proc)), encoding="utf-8"
    )
    (tmp_path / "proj/src/main/java/com/x").mkdir(parents=True, exist_ok=True)
    return src


def test_an_item_no_data_entry_declares_is_named_undeclared_not_no_such_item(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    stub = "package com.x.service;\npublic class TWService {\n    public void run() {}\n}\n"
    prog = _program(tmp_path, ["    MOVE DB2-CODFUN TO WS-MSG", "    PERFORM TRATA-SQLCODE", "    GOBACK."])
    r = P.translate(prog, [], stub, "com.x", {}, tmp_path / "proj")
    holes = " | ".join(r.stats["holes"])
    assert "DB2-CODFUN: undeclared item" in holes and "TRATA-SQLCODE: undeclared paragraph" in holes, holes
    assert "no such" not in holes


def test_the_translator_supplied_interface_blocks_stay_a_translator_gap():
    from gitgalaxy.tools.cobol_to_java.det import gen as G

    assert G._missing_item("DIBSTAT") == "no such item" and G._missing_item("EIBCALEN") == "no such item"
    assert G._missing_item("SQLCA") == "undeclared item"
