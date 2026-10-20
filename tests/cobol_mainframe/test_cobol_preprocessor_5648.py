"""#5648 / #5645: the COPY statement rule, its statement end and REPLACING live once in core.cobol_preprocessor, and the
translator (det/source.py) and the scanner (mainframe_boundary, galaxy_ir) both use it. Every COPY spelling resolves
the same way on both sides: unquoted, quoted, and a quoted file literal with its extension (`COPY "ws-state.cpy".`),
with `OF|IN library` and `REPLACING`, in fixed and free format. Our own fixtures only."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.core import cobol_preprocessor as PP  # noqa: E402
from gitgalaxy.core import mainframe_boundary as MB  # noqa: E402
from gitgalaxy.tools.cobol_to_cobol import galaxy_ir as GIR  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402


def _one(text: str) -> PP.CopyStatement:
    found = list(PP.copy_statements(text))
    assert len(found) == 1, found
    return found[0]


# ---- the statement rule ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "spelling, member, file_name",
    [
        ("COPY WSSTATE.", "WSSTATE", ""),
        ('COPY "WSSTATE".', "WSSTATE", ""),
        ("COPY 'ws-state'.", "WS-STATE", ""),
        ('COPY "ws-state.cpy".', "WS-STATE", "ws-state.cpy"),
        ("COPY 'ws-state.cpy'.", "WS-STATE", "ws-state.cpy"),
        ('copy "Ws-State.CPY".', "WS-STATE", "Ws-State.CPY"),
        ("COPY KUNDEÅ.", "KUNDEÅ", ""),
    ],
)
def test_every_spelling_names_its_member(spelling, member, file_name):
    c = _one("       01 G.  " + spelling)
    assert (c.member, c.file_name, c.library) == (member, file_name, "")
    assert spelling.startswith(("COPY", "copy")) and c.start == len("       01 G.  ")


@pytest.mark.parametrize("lib", ["OF CPYLIB", "IN CPYLIB", "IN 'CPYLIB'", 'OF "cpylib"'])
def test_the_library_follows_any_text_name(lib):
    for name in ("WSSTATE", '"ws-state.cpy"', "'WSSTATE'"):
        text = f"COPY {name} {lib} REPLACING ==:T:== BY ==X==."
        c = _one(text)
        assert c.library == "CPYLIB" and text[c.end :].startswith(" REPLACING")


def test_an_extension_needs_the_closing_quote_and_copy_is_a_whole_word():
    assert list(PP.copy_statements('COPY "ws-state.cpy.')) == []  # unterminated: no statement
    assert list(PP.copy_statements("MOVE XCOPY A TO B")) == []
    assert list(PP.copy_statements("MOVE WS-COPY A")) == []
    assert [c.member for c in PP.copy_statements("COPY A. COPY 'b.cpy'.")] == ["A", "B"]
    assert PP.COPY_ALONE.search("       01 G.  COPY") and not PP.COPY_ALONE.search("COPY A")


def test_the_statement_ends_at_its_separator_period_only():
    text = "COPY M REPLACING ==A.== BY ==B. C==  'x. y' BY 'z'. MOVE"
    assert text[: PP.statement_end(text, 0)].endswith("'z'.")
    assert PP.statement_end('COPY "m.cpy"', 0) == -1  # the period of `.cpy` is no separator
    assert PP.statement_end('COPY "m.cpy".', 0) == len('COPY "m.cpy".')


def test_replacing_after_a_file_literal_parses_and_applies_in_one_pass():
    text = 'COPY "t.cpy" REPLACING ==:TAG:== BY ==EMP== LEADING ==PF== BY ==NW== A-1 BY B-1 B-1 BY C-1.'
    c = _one(text)
    pairs = PP.copy_replacing(text, c.end)
    assert pairs == [[":TAG:", "EMP"], ["PF", "NW", "LEADING"], ["A-1", "B-1"], ["B-1", "C-1"]]
    assert PP.replace_text("05 :TAG:-ID PF-X A-1 B-1 XA-1", pairs) == "05 EMP-ID NW-X B-1 C-1 XA-1"


def test_the_scanner_and_the_translator_share_one_rule():
    assert MB._copy_replacing is PP.copy_replacing and GIR._replace_text is PP.replace_text
    assert SRC.statement_end is PP.statement_end and SRC.copy_replacing is PP.copy_replacing


# ---- the translator: the member is found, expanded and translated ----------------------------------------------------
HEAD = ("IDENTIFICATION DIVISION.", "PROGRAM-ID. PROG.", "DATA DIVISION.", "WORKING-STORAGE SECTION.")
TAIL = ("PROCEDURE DIVISION.", "    MOVE 'AB' TO :TAG:-NAME.", "    GOBACK.")


def _fixed(*body: str) -> str:
    return "".join(f"       {b}\n" for b in body)


def _free(*body: str) -> str:
    return "       >>SOURCE FORMAT FREE\n" + "".join(f"{b} *> free\n" for b in body)


def _program(tmp_path: Path, form, copy: str, member: str = "ws-state.cpy") -> Path:
    (tmp_path / "copy").mkdir()
    (tmp_path / "copy" / member).write_text(_fixed("01 :TAG:-REC.", "   05 :TAG:-NAME PIC X(8)."), encoding="utf-8")
    prog = tmp_path / "PROG.cbl"
    tail = [t.replace(":TAG:", "WS") for t in TAIL]
    prog.write_text(form(*HEAD, copy, *tail), encoding="utf-8")
    return prog


@pytest.mark.parametrize("form", [_fixed, _free], ids=["fixed", "free"])
@pytest.mark.parametrize(
    "copy",
    [
        'COPY "ws-state.cpy" REPLACING ==:TAG:== BY ==WS==.',
        "COPY 'ws-state.cpy' IN CPYLIB REPLACING ==:TAG:== BY ==WS==.",
        "COPY WS-STATE REPLACING ==:TAG:== BY ==WS==.",
    ],
)
def test_the_quoted_copybook_is_expanded(tmp_path, form, copy):
    prog = _program(tmp_path, form, copy)
    text = [ln.text.strip() for ln in SRC.program_lines(prog, [tmp_path / "copy"])]
    assert "05 WS-NAME PIC X(8)." in text and not any("COPY" in t for t in text)
    assert SRC.copy_names(SRC.logical_lines(prog.read_text().splitlines(), str(prog))) == {"WS-STATE"}


def test_a_file_literal_finds_an_extension_no_list_holds(tmp_path):
    prog = _program(tmp_path, _fixed, "COPY 'state.inc' REPLACING ==:TAG:== BY ==WS==.", member="state.inc")
    text = [ln.text.strip() for ln in SRC.program_lines(prog, [tmp_path / "copy"])]
    assert "05 WS-NAME PIC X(8)." in text


def test_a_missing_file_literal_is_refused_by_name(tmp_path):
    prog = _program(tmp_path, _fixed, 'COPY "nothere.cpy".')
    with pytest.raises(SRC.CopyNotFound, match="COPY NOTHERE"):
        SRC.program_lines(prog, [tmp_path / "copy"])


def test_a_program_naming_its_copybook_by_file_literal_translates(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    prog = _program(tmp_path, _fixed, 'COPY "ws-state.cpy" REPLACING ==:TAG:== BY ==WS==.')
    stub = "package com.x.service;\npublic class PROGService {\n}\n"
    r = P.translate(prog, [tmp_path / "copy"], stub, "com.x", {}, None)
    assert (r.stats["translated"], r.stats["holes"]) == (r.stats["statements"], [])
    assert "WS_NAME" in r.java.upper().replace("-", "_")


# ---- #5648 slice 2: the scanner's COPY / EXEC SQL INCLUDE head scan is the shared rule ---------------------------------
def test_the_scanner_uses_the_shared_head_and_library_rules():
    assert MB._COPY_IN_ENTRY is PP.COPY_OR_INCLUDE_HEAD
    assert MB._COPY_LIBRARY is PP.COPY_LIBRARY


@pytest.mark.parametrize(
    "text, member, library",
    [
        ("COPY INQCUST.", "INQCUST", ""),
        ("copy inqcust.", "INQCUST", ""),
        ('COPY "ws-state.cpy".', "WS-STATE", ""),
        ("COPY 'ws-state.cpy' IN SHRCPY.", "WS-STATE", "SHRCPY"),
        ("COPY DATEWS OF SHRCPY.", "DATEWS", "SHRCPY"),
        ("COPY\n    DATEWS\n    IN  SHRCPY.", "DATEWS", "SHRCPY"),
        ("EXEC SQL INCLUDE SQLCA END-EXEC.", "SQLCA", ""),
        ("exec sql\n  include LGCMAREA end-exec.", "LGCMAREA", ""),
        ('COPY "pd-level.cpy" REPLACING ==:T:== BY ==X==.', "PD-LEVEL", ""),
    ],
)
def test_head_and_library_read_every_spelling(text, member, library):
    m = PP.COPY_OR_INCLUDE_HEAD.search(text)
    assert m and m.group(1).upper() == member
    lib = PP.COPY_LIBRARY.match(text, m.end())
    assert (lib.group(1).upper() if lib else "") == library


@pytest.mark.parametrize("text", ["XCOPY FOO.", "MY-COPY FOO.", "EXEC SQL SELECT 1 END-EXEC.", "COPYRIGHT X."])
def test_head_ignores_words_that_only_contain_copy(text):
    assert PP.COPY_OR_INCLUDE_HEAD.search(text) is None
