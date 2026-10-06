"""#4462: what the det translator reads before it parses -- the code page the estate declares (estate-crucible
`key/manifest.json` `code_pages`, which the engine reads through `--source-encoding`), free-format source, and the
text it refuses by name instead of crashing (national / DBCS text, a national letter in a name, DECIMAL-POINT IS
COMMA)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.core.ebcdic_codecs import register  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

register()  # cp277 and the other national EBCDIC pages


def _fixed(*body: str) -> str:
    return "".join(f"       {b}\n" for b in body)


HEAD = ("IDENTIFICATION DIVISION.", "PROGRAM-ID. PROG.", "DATA DIVISION.", "WORKING-STORAGE SECTION.")


def _lines(*body: str) -> list:
    return [SRC.Line(t, "/x/PROG.cbl", n) for n, t in enumerate((*HEAD, *body), 1)]


def _ebcdic_estate(tmp_path, codec="cp277"):
    """cbl/PROG.cbl and cpy/KUNDEÅ.cpy in raw EBCDIC (NEL line ends), as estate-crucible NORD ships them."""
    root = tmp_path / "estate"
    (root / "cbl").mkdir(parents=True)
    (root / "cpy").mkdir()
    prog = root / "cbl" / "PROG.cbl"
    text = _fixed(*HEAD, "01  KUNDE-DATA.", "COPY 'KUNDEÅ'.", "01  NAVN PIC X(4) VALUE 'ÆØÅ'.",
                  "PROCEDURE DIVISION.", "    MOVE 'Å' TO NAVN", "    GOBACK.")  # fmt: skip
    prog.write_bytes(text.replace("\n", "\x85").encode(codec))
    (root / "cpy" / "KUNDEÅ.cpy").write_bytes(_fixed("05  KUNDE-NR PIC X(8).").replace("\n", "\x85").encode(codec))
    deps = {"cbl/PROG.cbl": ["cpy/KUNDEÅ.cpy"], "cpy/KUNDEÅ.cpy": []}
    pages = {"cbl/PROG.cbl": codec, "cpy/KUNDEÅ.cpy": codec}
    return prog, root, deps, pages


def test_the_declared_code_page_decodes_the_program_and_its_members(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    prog, root, deps, pages = _ebcdic_estate(tmp_path)
    eng = SRC.EngineCopies.of(prog, root, deps, pages=pages)
    lines = SRC.program_lines(prog, [], eng)
    assert any(ln.text.strip() == "05  KUNDE-NR PIC X(8)." for ln in lines)  # COPY 'KUNDEÅ' found and decoded
    recs = {it.name: it for r in L.parse(lines) for it in r.walk()}
    assert recs["KUNDE-NR"].size == 8 and recs["NAVN"].values == [("lit", "ÆØÅ")]
    move = ST.parse(lines).paragraphs[0].body[0]
    assert move.kind == "MOVE" and move.data["from"].value == "Å"
    # undeclared, the bytes are a guess (cp1252): no IDENTIFICATION DIVISION is read at all
    unaided = SRC.EngineCopies.of(prog, root, deps)
    with pytest.raises(SRC.CopyNotFound):
        SRC.program_lines(prog, [], unaided)


def test_engine_copies_carry_the_pages_from_the_ir_and_the_port_ticket(tmp_path):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import GalaxyIR

    files = {"cbl/P.cbl": NS(copy_deps=["cpy/A.cpy"], copy_dep_libraries={}),
             "cpy/A.cpy": NS(copy_deps=[], copy_dep_libraries={}),
             "cbl/Q.cbl": NS(copy_deps=[], copy_dep_libraries={})}  # fmt: skip
    pages = {"cbl/P.cbl": "cp273", "cpy/A.cpy": "cp273", "cbl/Q.cbl": "cp037"}
    ir = NS(files=files, copy_member_gaps=None, copy_member_collisions=None, source_page=pages.get)
    ir.copy_resolution = lambda p: GalaxyIR.copy_resolution(ir, p)
    assert GalaxyIR.copy_pages(ir, "cbl/P.cbl") == {"cbl/P.cbl": "cp273", "cpy/A.cpy": "cp273"}
    ir.copy_pages = lambda p: GalaxyIR.copy_pages(ir, p)
    eng = SRC.engine_copies_from_ir(ir, "cbl/P.cbl", tmp_path)
    assert eng.page(tmp_path / "cpy/A.cpy") == "cp273" and eng.page(tmp_path / "cbl/Q.cbl") is None

    prog, root, deps, pages = _ebcdic_estate(tmp_path)
    jobs = tmp_path / "project" / "ai_agent_jobs"
    jobs.mkdir(parents=True)
    ticket = {"source": {"program": {"file": "cbl/PROG.cbl"}, "copybooks": []},
              "facts": {"program": {"copy_edges": {"cbl/PROG.cbl": {"cpy/KUNDEÅ.cpy": []}, "cpy/KUNDEÅ.cpy": {}},
                                    "copy_pages": pages}}}  # fmt: skip
    (jobs / "PROG_port_ticket.json").write_text(json.dumps(ticket), encoding="utf-8")
    eng = SRC.engine_copies_from_ticket(tmp_path / "project", prog)
    assert eng.page(prog) == "cp277"
    assert any("KUNDE-NR" in ln.text for ln in SRC.program_lines(prog, [], eng))


@pytest.mark.parametrize(
    "body, why",
    [
        # estate-crucible KYUYJP (UTF-8): a Kanji name -- it raised UnicodeEncodeError from layout.parse / stmt.parse
        (("01  社員コード PIC X(6).", "PROCEDURE DIVISION.", "    MOVE '000001' TO 社員コード", "    GOBACK."),
         r"PROG\.cbl:5: national / DBCS text \('社', U\+793E\) is not modelled"),
        (("01  F02 PIC X.", "PROCEDURE DIVISION.", "    MOVE '漢字' TO F02", "    GOBACK."),
         r"PROG\.cbl:7: national / DBCS text"),
        (("01　F02 PIC X.", "PROCEDURE DIVISION.", "    GOBACK."), r"U\+3000"),  # an ideographic space
        # ZINSBER read in cp273: a national letter in a name the grammar cannot read (it refused the line unnamed)
        (("01  BETRÄGE PIC 9(3).", "PROCEDURE DIVISION.", "    GOBACK."),
         r"PROG\.cbl:5: the name BETRÄGE holds a national letter"),
        (("01  B PIC X(4).", "PROCEDURE DIVISION.", "    MOVE 'Ä' TO GEBÜHR", "    GOBACK."), r"the name GEBÜHR"),
        # ZINSBER: `VALUE 1000,00` / `MOVE 0,5`: never read as integers
        (("01  B PIC 9(7)V99 VALUE 1000,00.", "PROCEDURE DIVISION.", "    MOVE 0,5 TO B", "    GOBACK."), None),
    ],
)  # fmt: skip
def test_text_the_translator_cannot_read_is_refused_by_name(body, why):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = _lines(*body)
    if why is None:  # DECIMAL-POINT IS COMMA
        lines = _lines("01  B PIC X.")[:2] + [SRC.Line(t, "/x/PROG.cbl", 0) for t in (
            "ENVIRONMENT DIVISION.", "CONFIGURATION SECTION.", "SPECIAL-NAMES.", "    DECIMAL-POINT IS COMMA.")] + \
            _lines(*body)[2:]  # fmt: skip
        why = "DECIMAL-POINT IS COMMA is not modelled"
    with pytest.raises(L.LayoutError, match=why):
        L.parse(lines)
    with pytest.raises(E.ExprError, match=why):
        ST.parse(lines)


def test_national_text_in_a_comment_or_a_latin1_literal_is_read():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L

    raw = _fixed(*HEAD, "01  B PIC X(4) VALUE 'ÆØÅ'.", "PROCEDURE DIVISION.", "    GOBACK.").splitlines()
    raw.insert(1, "      * KYUYO01 - 給与計算 (CP930)")
    raw.insert(3, "       AUTHOR. 山田 / JØRGEN.")  # (free text no parser reads)
    lines = SRC.logical_lines(raw, "/x/PROG.cbl")
    assert SRC.unmodelled(lines) is None
    assert [it.values for r in L.parse(lines) for it in r.walk()] == [[("lit", "ÆØÅ")]]


def test_free_format_source_is_read():
    """estate-crucible MODRATE / PCEDFREE: `>>SOURCE FORMAT FREE`, code from column 1, `*>` comments."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    raw = [
        "       >>SOURCE FORMAT FREE",
        "IDENTIFICATION DIVISION.",
        "PROGRAM-ID.    MODRATE.",
        "*> ------------------------------------------------------------",
        "DATA DIVISION.",
        "WORKING-STORAGE SECTION.",
        "    01  WS-FOUND               PIC X VALUE 'N'.  *> found yet",
        "    01  WS-MSG PIC X(20) VALUE 'a *> b'.                                     *> past column 72",
        "PROCEDURE DIVISION.",
        "MAIN-PARA.",
        "    MOVE 'Y' TO WS-FOUND",
        "    GOBACK.",
        ">>SOURCE FORMAT IS FIXED",
        "       LAST-PARA.",
        "      * a fixed-format comment again",
        "           GOBACK.",
    ]  # fmt: skip
    lines = SRC.logical_lines(raw, "/x/MODRATE.cbl")
    assert [ln.line for ln in lines] == [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16]
    assert lines[4].text == "    01  WS-FOUND               PIC X VALUE 'N'."
    items = {it.name: it for r in L.parse(lines) for it in r.walk()}
    assert items["WS-MSG"].values == [("lit", "a *> b")]  # (a `*>` inside a literal is no comment)
    proc = ST.parse(lines)
    assert [p.name for p in proc.paragraphs] == ["MAIN-PARA", "LAST-PARA"]
    assert [s.line for s in proc.paragraphs[0].body] == [11, 12]
