"""det-port translator pieces that need no corpus: COBOL conditions and expressions (det/expr.py), statement parsing
(det/stmt.py) and EXEC CICS options (det/cics.py). Each case is a COBOL rule the proofs of the det ports depend on;
the ports themselves are proven by tests/tools/det_port.py against GnuCOBOL."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402


def R(name: str) -> E.Ref:  # noqa: N802 -- a Ref, as the AST writes it
    return E.Ref(name)


def test_abbreviated_relation_repeats_subject_and_operator():
    c = E.parse_condition("A = 1 OR 2")
    assert c == E.Or(E.Rel("=", R("A"), E.Lit(Decimal(1))), E.Rel("=", R("A"), E.Lit(Decimal(2))))


def test_abbreviated_not_applies_to_every_object():
    # A NOT = 'Y' AND 'N' is A NOT = 'Y' AND A NOT = 'N'
    c = E.parse_condition("A NOT = 'Y' AND 'N'")
    assert c == E.And(E.Not(E.Rel("=", R("A"), E.Lit("Y"))), E.Not(E.Rel("=", R("A"), E.Lit("N"))))


def test_abbreviated_data_name_objects_carry_the_relation():
    # EIBAID NOT = DFHENTER AND DFHPF7 AND DFHPF3: DFHPF7 / DFHPF3 are objects unless they are condition-names
    c = E.parse_condition("EIBAID NOT = DFHENTER AND DFHPF7 AND DFHPF3")
    assert c.right.abbrev == ("=", R("EIBAID"), True)
    assert c.left.right.abbrev == ("=", R("EIBAID"), True)


def test_dfhresp_is_its_resp_value():
    assert E.parse_condition("WS-RESP-CD = DFHRESP(NOTFND)") == E.Rel("=", R("WS-RESP-CD"), E.Lit(Decimal(13)))


def test_dfhvalue_is_its_cvda():
    # IBM CICS TS API Reference, CVDAs and numeric values: UCTRAN 450, IMMEDIATE 2
    assert E.parse_condition("WS-X = DFHVALUE(UCTRAN)") == E.Rel("=", R("WS-X"), E.Lit(Decimal(450)))
    assert E.parse_arith("DFHVALUE(IMMEDIATE)") == E.Lit(Decimal(2))


def test_arithmetic_precedence_and_signed_literal():
    e = E.parse_arith("A + B * 2 ** 3 - -1")
    assert e == E.Bin(
        "-", E.Bin("+", R("A"), E.Bin("*", R("B"), E.Bin("**", E.Lit(Decimal(2)), E.Lit(Decimal(3))))),
        E.Lit(Decimal(-1)),
    )  # fmt: skip


def test_class_condition_with_reference_modification():
    c = E.parse_condition("WS-DATE(1:4) NOT NUMERIC")
    assert isinstance(c, E.ClassCond) and c.negated and c.operand.refmod == (E.Lit(Decimal(1)), E.Lit(Decimal(4)))


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("INSPECT X TALLYING I FOR ALL 'S' ALL 'U'", [("tally", "ALL"), ("tally", "ALL")]),
        ("INSPECT X REPLACING ALL 'S' BY '1' ALL 'U' BY '1' CHARACTERS BY '0'",
         [("replace", "ALL"), ("replace", "ALL"), ("replace", "CHARACTERS")]),
        ("INSPECT X CONVERTING 'abc' TO 'ABC'", [("convert", None)]),
        ("INSPECT X TALLYING I FOR LEADING SPACES REPLACING FIRST 'A' BY 'B' AFTER INITIAL 'C'",
         [("tally", "LEADING"), ("replace", "FIRST")]),
    ],
)  # fmt: skip
def test_inspect_clauses(text, kinds):
    s = S._statement(text, 1)
    assert s.kind == "INSPECT"
    got = [(c[0], c[2] if c[0] == "tally" else c[1] if c[0] == "replace" else None) for c in s.data["clauses"]]
    assert got == kinds


def test_perform_varying():
    s = S._statement("PERFORM P1 VARYING I FROM 1 BY 1 UNTIL I > 10", 1)
    assert s.kind == "PERFORM" and s.data["target"] == "P1" and s.data["varying"][0] == R("I")


def test_exec_cics_options():
    words, opts = C.parse_exec(
        "EXEC CICS SEND MAP('COSGN0A') MAPSET('COSGN00') FROM(COSGN0AO) ERASE CURSOR RESP(WS-RESP) END-EXEC"
    )
    assert words == ["SEND"]
    assert opts == {"MAP": "'COSGN0A'", "MAPSET": "'COSGN00'", "FROM": "COSGN0AO", "ERASE": None, "CURSOR": None,
                    "RESP": "WS-RESP"}  # fmt: skip


def test_exec_cics_two_word_verb_and_nested_parentheses():
    words, opts = C.parse_exec("EXEC CICS HANDLE ABEND LABEL(ABEND-ROUTINE) END-EXEC")
    assert words == ["HANDLE", "ABEND"] and opts == {"LABEL": "ABEND-ROUTINE"}
    _, opts = C.parse_exec("EXEC CICS READ DATASET(F) RIDFLD(K) KEYLENGTH(LENGTH OF K(1:4)) END-EXEC")
    assert opts["KEYLENGTH"] == "LENGTH OF K(1:4)"


def test_syncpoint_rollback_is_a_rollback():
    words, opts = C.parse_exec("EXEC CICS SYNCPOINT ROLLBACK END-EXEC")
    assert " ".join(words) == "SYNCPOINT ROLLBACK" and opts == {}


def test_statements_keep_their_source_lines_past_a_multi_line_exec_block(tmp_path):
    """A statement's line is its source line (the Db2 repositories' methods are found by it): a multi-line EXEC
    block before it must not shift it, and the block's own period must still end its sentence."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    src = "\n".join([
        "       IDENTIFICATION DIVISION.", "       PROGRAM-ID. LINES.", "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.", "       01 A PIC X.", "       PROCEDURE DIVISION.", "       P1.",
        "           EXEC SQL", "               DELETE FROM T", "               WHERE C = 1", "           END-EXEC.",
        "           MOVE 'X' TO A.", "       P2.", "           EXEC CICS RETURN", "           END-EXEC.",
        "           MOVE 'Y' TO A.",
    ]) + "\n"  # fmt: skip
    (tmp_path / "LINES.cbl").write_text(src)
    proc = S.parse(SRC.program_lines(tmp_path / "LINES.cbl", []))
    assert [p.name for p in proc.paragraphs] == ["P1", "P2"]
    p1, p2 = proc.paragraphs
    assert [(s.kind, s.line) for s in p1.body] == [("EXEC", 8), ("MOVE", 12)]
    assert [(s.kind, s.line) for s in p2.body] == [("EXEC", 14), ("MOVE", 16)]


def test_a_when_condition_keeps_its_leading_not():
    """EVALUATE TRUE WHEN NOT A AND B = C: NOT is the condition's own -- (NOT A) AND B = C. Only a value or a range
    takes WHEN NOT as its negation (COTRTUPC's NOT CDEMO-PGM-REENTER AND CDEMO-FROM-PROGRAM = LIT-ADMINPGM)."""
    obj = S._when_object("NOT A-FLAG AND B = C")
    assert obj == ("COND", E.And(E.Not(E.CondName(R("A-FLAG"))), E.Rel("=", R("B"), R("C"))), None, False)
    assert S._when_object("NOT 5") == ("VALUE", E.Lit(Decimal(5)), None, True)
    assert S._when_object("NOT 1 THRU 9")[0] == "RANGE" and S._when_object("NOT 1 THRU 9")[3] is True


def test_each_entry_runs_with_its_programs_trunc(tmp_path):
    """#4102: TRUNC(STD) is IBM's default; a program's CBL card or the compile PARM says otherwise. Each entry swaps it
    in and restores the caller's, so a LINK into a program compiled otherwise leaves the caller's as it was."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "T.cbl"
    src.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T.\n", encoding="ascii")
    assert P.trunc_std(src) is True
    assert P.trunc_std(src, ["TRUNC(BIN)"]) is False
    src.write_text("       PROCESS TRUNC(STD)\n       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T.\n", encoding="ascii")
    assert P.trunc_std(src, ["TRUNC(BIN)"]) is True  # the program's own card wins
    java = ("class S {\n    public void runTask(CicsTask task) {\n        x(\"{\");\n        return;\n    }\n"
            "    void other() {\n    }\n}\n")
    out = P.with_trunc(java, True)
    assert "boolean truncBefore = Cobol.swapTruncBinary(true);  // TRUNC(STD)" in out
    assert out.index("finally") < out.index("void other()") and 'x("{");' in out
