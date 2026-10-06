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


# ---- #4462 slice 2 -------------------------------------------------------------------------------------------------
def _rows(*rows: str) -> list[str]:
    """Fixed-format rows: `-` first is a continuation row (indicator column 7), else code from column 8."""
    return [("      " + r) if r.startswith("-") else ("       " + r) for r in rows]


def _hex_continued(lead: str, q: str, digits: str, tail: str) -> list[str]:
    """`lead` X<q>digits... run to column 72, continued on the next row (its quote in column 12) up to `tail`."""
    first = f"{lead}X{q}"
    room = 65 - len(first)
    return [first + digits[:room], f"-    {q}{digits[room:]}{q}{tail}"]


@pytest.mark.parametrize("q", ["'", '"'])
def test_a_continued_hex_literal_parses_in_either_quote_style(q):
    """X'...' continued onto a second row: the grammar continues no hex literal (both quote styles were refused,
    the VALUE and the MOVE); it is handed an alphanumeric stand-in and the readers get X'...' back."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    digits = "C1C2C3C4F0F1F2F3" * 5  # 40 bytes
    raw = _rows(*HEAD, *_hex_continued("01 F PIC X(40) VALUE ", q, digits, "."), "01 A PIC X(40).",
                "PROCEDURE DIVISION.", "P1.", *_hex_continued("    MOVE ", q, digits, " TO A"),
                f"    IF A = X{q}C1{q} DISPLAY 'C1' END-IF", "    GOBACK.")  # fmt: skip
    lines = SRC.logical_lines(raw, "/x/PROG.cbl")
    want = bytes.fromhex(digits)
    assert L.parse(lines)[0].values == [("hex", want)]
    body = ST.parse(lines).paragraphs[0].body
    assert body[0].kind == "MOVE" and body[0].data["from"] == E.Lit(want)
    assert body[1].data["cond"].right == E.Lit(b"\xc1")


def test_a_lower_case_hex_literal_is_read():
    """GenApp lgtestc1: `Inspect COMM-AREA Replacing All x'00' by x'40'` (the grammar reads X'00' only)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = _lines("01  B PIC X(2) VALUE x'C1C2'.", "PROCEDURE DIVISION.", "    Inspect B Replacing All x'00' by x'40'",
                   "    GOBACK.")  # fmt: skip
    assert L.parse(lines)[0].values == [("hex", b"\xc1\xc2")]
    st = ST.parse(lines).paragraphs[0].body[0]
    assert st.kind == "INSPECT" and "X'00'" in st.text and "X'40'" in st.text
    assert SRC.unwrap(SRC.as_fixed(lines)).count("x'") == 0


def test_the_hex_stand_in_is_refused_by_name_in_the_source():
    assert "U+001F" in SRC.unmodelled(_lines(f"    MOVE '{SRC.HX}C1' TO A."))


IDMS = (  # estate-crucible LOAN LNIDMS01, its shape
    "IDENTIFICATION DIVISION.", "PROGRAM-ID.    LNIDMS01.", "ENVIRONMENT DIVISION.", "IDMS-CONTROL SECTION.",
    "PROTOCOL.    MODE IS IDMS-DC DEBUG", "             IDMS-RECORDS MANUAL.", "DATA DIVISION.", "SCHEMA SECTION.",
    "DB LOANSS01 WITHIN LOANSCHM.", "WORKING-STORAGE SECTION.", "01  WS-LOAN-KEY            PIC X(12).",
    "PROCEDURE DIVISION.", "0000-MAIN.", "    BIND RUN-UNIT", "    OBTAIN CALC LOAN", "    FINISH", "    DC RETURN.",
)  # fmt: skip


@pytest.mark.parametrize("drop", [None, "IDMS-CONTROL", "SCHEMA"])
def test_an_idms_program_is_refused_by_name(drop):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    body = [t for t in IDMS if drop is None or not t.startswith(drop)]
    if drop == "IDMS-CONTROL":
        body = [t for t in body if "IDMS-" not in t or "SECTION" in t]
    lines = [SRC.Line(t, "/x/LNIDMS01.cbl", n) for n, t in enumerate(body, 1)]
    with pytest.raises(L.LayoutError, match=r"LNIDMS01\.cbl:\d+: IDMS DML not supported"):
        L.parse(lines)
    with pytest.raises(E.ExprError, match="IDMS DML not supported"):
        ST.parse(lines)


MULTI = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    MULTI.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STATUS              PIC X(2) VALUE 'OK'.
       PROCEDURE DIVISION.
       MAINLINE SECTION.
       0100.
           PERFORM 0200
           CALL 'INNER'
           CALL 'SIBLING'
           GOBACK.
       0200.
           MOVE 'E1' TO WS-STATUS.
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    INNER IS COMMON.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-I                   PIC 9(4) COMP VALUE 0.
       PROCEDURE DIVISION.
       1000-CALC.
           ADD 1 TO WS-I
           GOBACK.
       END PROGRAM INNER.
       END PROGRAM MULTI.
       IDENTIFICATION DIVISION.
        PROGRAM-ID. 'SIBLING'.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-LINES               PIC 9(4) VALUE 7.
       PROCEDURE DIVISION.
       0100.
           ADD 1 TO WS-LINES
           DISPLAY 'SIBLING ' WS-LINES
           GOBACK.
       END PROGRAM 'SIBLING'.
"""  # estate-crucible PAYMAIN's shape (PAYCALC nested, PAYRPT batch-compiled after it), without its COPY collision


def test_a_multi_program_source_splits_into_its_programs():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = SRC.logical_lines(MULTI.splitlines(), "/x/MULTI.cbl")
    units = SRC.program_units(lines)
    assert [(u.name, u.parent) for u in units] == [("MULTI", None), ("INNER", "MULTI"), ("SIBLING", None)]
    assert [(u.lines[0].line, u.lines[-1].line) for u in units] == [(1, 14), (15, 23), (26, 35)]
    want = {"MULTI": (["WS-STATUS"], ["MAINLINE", "0100", "0200"]), "INNER": (["WS-I"], ["1000-CALC"]),
            "SIBLING": (["WS-LINES"], ["0100"])}  # fmt: skip
    for u in units:
        assert ([r.name for r in L.parse(u.lines)], [p.name for p in ST.parse(u.lines).paragraphs]) == want[u.name]
        assert SRC.program_unit(lines, u.name.lower()) == u.lines
    assert SRC.program_unit(lines) == units[0].lines


def test_a_multi_program_source_is_never_parsed_as_one_program():
    """Before #4462 the parsers read the first program's records and paragraphs and dropped the rest unnamed."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = SRC.logical_lines(MULTI.splitlines(), "/x/MULTI.cbl")
    why = r"several programs in one source \(MULTI, INNER, SIBLING\)"
    with pytest.raises(L.LayoutError, match=why):
        L.parse(lines)
    with pytest.raises(E.ExprError, match=why):
        ST.parse(lines)
    single = SRC.logical_lines(MULTI.splitlines()[:14] + ["       END PROGRAM MULTI."], "/x/M.cbl")
    assert SRC.program_units(single)[0].lines is single and SRC.several_programs(single) is None


@pytest.mark.parametrize(
    "edit, why",
    [
        (("01  WS-STATUS              PIC X(2) VALUE 'OK'.", "01  WS-STATUS PIC X(2) IS GLOBAL VALUE 'OK'."),
         "INNER is nested in MULTI, which declares GLOBAL items"),
        (("END PROGRAM INNER.", "END PROGRAM OTHER."), "END PROGRAM OTHER closes no open program"),
    ],
)  # fmt: skip
def test_a_unit_the_translator_cannot_read_alone_is_refused_by_name(edit, why):
    lines = SRC.logical_lines(MULTI.replace(*edit).splitlines(), "/x/MULTI.cbl")
    with pytest.raises(SRC.UnitRefused, match=why):
        SRC.program_unit(lines, "INNER")
    with pytest.raises(SRC.UnitRefused, match="no program NONE in the source"):
        SRC.program_unit(SRC.logical_lines(MULTI.splitlines(), "/x/MULTI.cbl"), "NONE")


def test_the_cross_check_reads_each_program_of_a_multi_program_source(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(ROOT / "tests" / "tools" / "referees"))
    sys.path.insert(0, str(ROOT / "tests" / "tools"))
    import translator_adapter as TA

    (tmp_path / "MULTI.cbl").write_text(MULTI, encoding="utf-8")
    r = TA.program_facts(tmp_path, tmp_path / "MULTI.cbl", [])
    assert r["status"] == "ok", r["error"]
    assert {"0100", "0200", "1000-CALC", "MAINLINE"} <= r["facts"]["units"]
    # each program's paragraphs end where the program does (0200 had run on through INNER and SIBLING)
    assert {"0200 L13-14", "1000-CALC L21-23"} <= r["facts"]["unit_extents"]
    assert r["facts"]["data_items"] == {"L5 01 WS-STATUS", "L19 01 WS-I", "L30 01 WS-LINES"}
    assert r["facts"]["calls"] == {"CALL 'INNER'", "CALL 'SIBLING'"}


@pytest.mark.parametrize("using", ["", " USING PCB1"])
def test_entry_dlitcbl_is_read_and_is_the_programs_entry(using):
    """CardDemo DBUNLDGS / PAUDBLOD / PAUDBUNL, DSF R001BYDL (IMS DL/I batch): `ENTRY 'DLITCBL' USING pcb ...` as
    the first statement (the grammar has no ENTRY: the PROCEDURE DIVISION was refused)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = _lines("01  W PIC X.", "LINKAGE SECTION.", "01  PCB1 PIC X(10).", "01  PCB2 PIC X(10).",
                   f"PROCEDURE DIVISION{using}.", "MAIN-PARA.", "    ENTRY 'DLITCBL'  USING PCB1", "                         PCB2.",
                   "    DISPLAY 'IN'", "    ENTRY 'ALT' USING BY REFERENCE PCB2", "    GOBACK.")  # fmt: skip
    proc = ST.parse(lines)
    body = proc.paragraphs[0].body
    assert [s.kind for s in body] == ["ENTRY", "DISPLAY", "ENTRY", "GOBACK"]
    assert [s.line for s in body] == [11, 13, 14, 15]
    assert body[0].data["name"] == "DLITCBL" and [r.name for r in body[0].data["using"]] == ["PCB1", "PCB2"]
    assert proc.using == (["PCB1", "PCB2"] if not using else ["PCB1"])
    assert body[0].data.get("first") is (True if not using else None) and not body[2].data.get("first")


@pytest.mark.parametrize(
    "stmt, func, args, refmod",
    [
        ("MOVE FUNCTION CURRENT-DATE (1:4) TO B", "CURRENT-DATE", [], ("1", "4")),  # estate-crucible KØBREG
        ("MOVE FUNCTION CURRENT-DATE(5:2) TO B", "CURRENT-DATE", [], ("5", "2")),  # CardDemo CBIMPORT
        ("MOVE FUNCTION UPPER-CASE(A) (2:) TO B", "UPPER-CASE", ["A"], ("2", None)),
        ("MOVE FUNCTION CURRENT-DATE TO B", "CURRENT-DATE", [], None),
    ],
)  # fmt: skip
def test_a_reference_modification_of_an_intrinsic_function_is_read(stmt, func, args, refmod):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    lines = _lines("01  A PIC X(8).", "01  B PIC X(8).", "PROCEDURE DIVISION.", f"    {stmt}",
                   "    MOVE 'FUNCTION F (1:2)' TO B", "    GOBACK.")  # fmt: skip
    body = ST.parse(lines).paragraphs[0].body
    f = body[0].data["from"]
    assert f.name == func and [a.name for a in f.args if not isinstance(a, tuple)] == args
    mod = next((a[1] for a in f.args if isinstance(a, tuple)), None)
    got = None if mod is None else tuple(None if x is None else str(x.value) for x in mod)
    assert got == refmod
    assert body[1].data["from"].value == "FUNCTION F (1:2)"  # (a literal's text is never rewritten)


def test_move_all_of_a_hex_literal_is_read():
    """estate-crucible KØBREG `MOVE ALL X'00' TO WS-BUF` (a hole before: ALL took a quoted literal only)."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import expr as E
    from gitgalaxy.tools.cobol_to_java.det import stmt as ST

    body = (
        ST.parse(_lines("01  B PIC X(4).", "PROCEDURE DIVISION.", "    MOVE ALL X'00' TO B", "    GOBACK."))
        .paragraphs[0]
        .body
    )
    assert body[0].kind == "MOVE" and body[0].data["from"] == E.Fig("ALL", "\x00", hex=True)
