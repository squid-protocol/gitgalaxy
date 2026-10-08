"""ARITHMETIC-OSVS in the det port (#4287, oracle_assumptions C2): `cobc -std=ibm` truncates arithmetic intermediates
(cob_decimal_align) where its compile-time state says so; the det translator replays that state (det/osvs.py) and the
runtime truncates the same way (Cobol.align, Cobol.Dc).

The planning tests need no Docker. The end-to-end test runs one program through GnuCOBOL (the harness's oracle) and
through the det port; it needs EQUIVALENCE_E2E=1, Docker and a JDK 17."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import expr as E  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import osvs as O  # noqa: E402

# items by name: (scale, binary integer -- loaded without its places pushed)
ITEMS = {"A": (0, False), "B": (0, False), "C": (0, False), "XB": (0, True), "YB": (0, True), "Z": (0, False),
         "A2": (2, False), "ZB": (0, True), "Q3": (3, False), "I5": (5, False)}  # fmt: skip


def leaf(e):
    if isinstance(e, E.Func):
        return O.Leaf("FUNC", 0, True)
    scale, binary = ITEMS[e.name]
    return O.Leaf("ITEM", scale, not binary)


def length(_e):
    return 4


def aligns(plan: dict) -> list[int]:
    return [v[1] for k, v in plan.items() if k != O.PLANNED and v[0] == "ALIGN"]


def test_the_issues_quotient_is_aligned_to_the_receivers_places():
    # COMPUTE R = A / B * C, R PIC 999V99: A / B kept to dmax = 2 places, then times 300 -- 099.00 (#4287)
    q = E.parse_arith("A / B")
    expr = E.Bin("*", q, E.Ref("C"))
    plan = O.plan_compute(expr, [2], leaf, length)
    assert plan[id(q)] == ("ALIGN", 2)
    assert id(expr) not in plan  # the last operation: the receiver's store truncates it


def test_a_literal_on_the_right_does_not_load_so_nothing_is_aligned_before_it():
    # A / B * 3: the literal is a decimal constant, never loaded -- the quotient goes on exact (measured: 000.99)
    q = E.parse_arith("A / B")
    plan = O.plan_compute(E.Bin("*", q, E.Lit(E.NumLit("3"))), [2], leaf, length)
    assert aligns(plan) == []


def test_binary_integers_push_nothing_so_their_sum_takes_dmax():
    # COMPUTE R = XB + YB + Z, R PIC 999V99: XB + YB aligned to 2 places from scale 0 -- libcob drops two digits
    s = E.parse_arith("XB + YB")
    plan = O.plan_compute(E.Bin("+", s, E.Ref("Z")), [2], leaf, length)
    assert plan[id(s)] == ("ALIGN", 2)


def test_unary_minus_is_zero_minus_and_aligned_like_any_operation():
    # - A + A7 is (0 - A) + A7: the difference aligned to dmax (measured: 007.00 for A = 1, A7 = 7)
    e = E.parse_arith("- A + B")
    assert isinstance(e.left, E.Neg)
    plan = O.plan_compute(e, [2], leaf, length)
    assert plan[id(e.left)] == ("ALIGN", 2)


def test_a_product_with_a_literal_takes_dmax_not_its_scale():
    # A2 * 1.25 * ZB: the product (4 places) aligned to dmax 2 when ZB is loaded (measured: 156.00, not 156.25)
    p = E.parse_arith("A2 * 1.25")
    plan = O.plan_compute(E.Bin("*", p, E.Ref("ZB")), [2], leaf, length)
    assert plan[id(p)] == ("ALIGN", 2)


def test_constant_folding_keeps_cobcs_scale_and_identity():
    e = E.parse_arith("100 * 0.5 + Q3")
    plan = O.plan_compute(e, [5], leaf, length)
    folded = plan[id(e.left)]
    assert folded[0] == "FOLD" and folded[1] == O.Num(0, "50", 0)  # trailing zeros dropped: 50, scale 0
    # a written 0.03 and a folded 0.03 are two decimal constants (cb_lookup_literal compares the digits as written)
    assert O.Num.written("0.03").key != O.Num.folded(3, 2).key
    assert O.Num.written("1.25").key == O.Num.folded(125, 2).key


def test_an_earlier_evaluate_leaves_its_dmax_to_the_next_compute_of_the_sentence():
    e = E.parse_arith("- B + Q3")
    clean = O.plan_compute(e, [0], leaf, length)
    after = O.plan_compute(e, [0], leaf, length, dmax_in=5)
    assert clean[id(e.left)] == ("ALIGN", 3) and after[id(e.left)] == ("ALIGN", 5)


def test_conditions_are_built_right_to_left_and_share_the_stack():
    # IF A2 * A2 > 0 AND XB * Z + YB > 1000 (measured on the oracle's C: the second relation's product aligned to
    # dmax, the first one's to the stack's 4 -- the second relation was built first)
    c = E.parse_condition("A2 * A2 > 0 AND XB * Z + YB > 1000")
    r1 = O.Relation(c.left.left, c.left.right)
    r2 = O.Relation(c.right.left, c.right.right)
    O.plan_condition([[r1, r2]], leaf, length)
    assert aligns(r1.plan) == [4]
    prod = c.right.left.left
    assert r2.plan[id(prod)] == ("ALIGN", 2) and r2.plan[id(c.right.left)] == ("ALIGN", 2)


def test_two_integer_literals_compare_at_compile_time_and_are_not_walked():
    # EVALUATE TRUE WHEN 3 > 75000 ... : cb_false, so the second WHEN's walk sets dmax (3), not the first's (0)
    w1 = O.Relation(E.Lit(E.NumLit("3")), E.Lit(E.NumLit("75000")))
    e = E.parse_arith("Q3 ** 1")
    w2 = O.Relation(e, E.Ref("A"))
    out = O.plan_condition([[w1], [w2]], leaf, length, evaluate=True)
    assert w1.constant and not w1.decimal
    assert out is not None and out[0] == 3


PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. OSVS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A  PIC 9 VALUE 1.
       01 B  PIC 9 VALUE 3.
       01 C  PIC 999 VALUE 300.
       01 A7 PIC 9 VALUE 7.
       01 Z  PIC 9 VALUE 1.
       01 XB PIC 9(4) COMP VALUE 123.
       01 YB PIC 9(4) COMP VALUE 456.
       01 ZB PIC 9(4) COMP VALUE 100.
       01 A2 PIC 9V99 VALUE 1.25.
       01 Q3 PIC 9V999 VALUE 3.125.
       01 P0 PIC S9(7) COMP-3 VALUE 98765.
       01 R  PIC 999V99.
       01 R0 PIC 9(11).
       01 R5 PIC 9(9)V9(5).
       PROCEDURE DIVISION.
           COMPUTE R = A / B * C
           DISPLAY 'ISSUE ' R
           COMPUTE R = A / B * 3
           DISPLAY 'LITERAL ' R
           COMPUTE R = XB + YB + Z
           DISPLAY 'BINARY ' R
           COMPUTE R = - A + A7
           DISPLAY 'UNARY ' R
           COMPUTE R = A2 * 1.25 * ZB
           DISPLAY 'PRODUCT ' R
           COMPUTE R = (A / B) + (A / B) + (A / B)
           DISPLAY 'SUM ' R
           ADD XB YB TO R
           DISPLAY 'ADD ' R
           IF A / B * C > 99.5
               DISPLAY 'IF Y'
           ELSE
               DISPLAY 'IF N'
           END-IF
           COMPUTE R5 = Q3 - 1.25
           DISPLAY 'CONST1 ' R5
           COMPUTE R5 = (100 * 0.5) + (Q3 - 1.25)
           DISPLAY 'CONST2 ' R5.
           EVALUATE TRUE
               WHEN A2 > Q3 * 2 + R5
                   DISPLAY 'W1'
               WHEN R5 < 0.00001
                   DISPLAY 'W2'
           END-EVALUATE
           COMPUTE R0 = ((- P0) + Q3) + Q3 * 1.25
           DISPLAY 'LEAK ' R0.
           COMPUTE R0 = ((- P0) + Q3) + Q3 * 1.25
           DISPLAY 'CLEAN ' R0
           GOBACK.
"""

# what the oracle prints (measured 2026-10-07, GnuCOBOL 3.1.2 -std=ibm): exact decimal would give 09999, 00099,
# 58000, 00600, 15625, 00099, 58000+, ...; ARITHMETIC-OSVS truncates as det/osvs.py says
WANT = {"ISSUE": "09900", "LITERAL": "00099", "BINARY": "50100", "UNARY": "00700", "PRODUCT": "15600",
        "SUM": "00099", "IF": "N"}  # fmt: skip


def _java_ok() -> bool:
    import test_det_programs as T

    return T._java() is not None


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed"])
def test_intermediates_are_truncated_as_the_oracle_truncates_them(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_programs as T

    if not _java_ok():
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = T._cobol(PROGRAM, cob)
    got = T._java_run("osvs", PROGRAM, tmp_path, mode != "bytes")
    assert got == want, f"java {got!r} != cobol {want!r}"
    shown = dict(line.split(" ", 1) for line in want.splitlines() if " " in line)
    for k, v in WANT.items():
        assert shown[k] == v, (k, shown[k])
    # the EVALUATE leaves its dmax (5) to the next COMPUTE of the sentence: (0 - P0) aligned to 5 places loses it all
    assert shown["LEAK"] != shown["CLEAN"]
