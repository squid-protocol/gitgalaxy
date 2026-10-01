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
