"""#4035: the alphanumeric relation conditions of a program are listed, with the CobolCompare call, in its ticket.

#3986 gave every ticket a general rule and util/CobolCompare; the porting agent still had to find the
alphanumeric comparisons itself. relation_facts reads them off: IF, EVALUATE WHEN, PERFORM UNTIL and SEARCH
WHEN, abbreviated conditions carried forward, operands classed from the data items (program and copybooks);
class and sign conditions are not comparisons. condition_ranges lists the level-88 THRU ranges and
collating_sequence the PROGRAM COLLATING SEQUENCE / ALPHABET declarations.
"""

import json
import os
from pathlib import Path

import pytest

from gitgalaxy.core.relation_facts import collating_sequence, condition_ranges, relation_facts
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import (
    build_ticket,
    collating_sequence_rules,
    ticket_markdown,
)

DATA = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. T.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC X(5).
       01 WS-B PIC A(5).
       01 WS-N PIC 9(3).
       01 WS-P PIC S9(5) COMP-3.
       01 WS-E PIC ZZ9.
       01 WS-G.
          05 WS-G1 PIC X.
          05 WS-G2 PIC 9 COMP-3.
       01 WS-C PIC X.
          88 IS-LETTER VALUE 'A' THRU 'Z'.
          88 IS-Y VALUE 'Y'.
       01 WS-K PIC 9.
          88 SMALL-K VALUE 1 THRU 3.
       PROCEDURE DIVISION.
"""


def facts(body: str, copybooks: list[str] | None = None) -> list[dict]:
    return relation_facts(DATA + body, copybooks)


def one(body: str) -> dict:
    (row,) = facts(body)
    return row


def test_an_if_on_two_alphanumeric_items():
    r = one("           IF WS-A > WS-B CONTINUE END-IF.\n")
    assert (r["line"], r["context"], r["op"], r["kind"]) == (19, "IF", ">", "alphanumeric")
    assert (r["left_class"], r["right_class"], r["ordering"], r["abbreviated"]) == (
        "alphanumeric",
        "alphanumeric",
        True,
        False,
    )
    assert r["java"] == "CobolCompare.gt(WS-A, WS-B)"


@pytest.mark.parametrize(
    ("cond", "op", "java"),
    [
        ("WS-A = 'X'", "=", "CobolCompare.eq(WS-A, 'X')"),
        ("WS-A NOT = 'X'", "<>", "!CobolCompare.eq(WS-A, 'X')"),
        ("WS-A <> 'X'", "<>", "!CobolCompare.eq(WS-A, 'X')"),
        ("WS-A NOT > 'X'", "<=", "CobolCompare.le(WS-A, 'X')"),
        ("WS-A NOT < 'X'", ">=", "CobolCompare.ge(WS-A, 'X')"),
        ("WS-A >= 'X'", ">=", "CobolCompare.ge(WS-A, 'X')"),
        ("WS-A <= 'X'", "<=", "CobolCompare.le(WS-A, 'X')"),
        ("WS-A IS EQUAL TO 'X'", "=", "CobolCompare.eq(WS-A, 'X')"),
        ("WS-A IS GREATER THAN 'X'", ">", "CobolCompare.gt(WS-A, 'X')"),
        ("WS-A LESS THAN OR EQUAL TO 'X'", "<=", "CobolCompare.le(WS-A, 'X')"),
        ("WS-A IS NOT GREATER THAN OR EQUAL TO 'X'", "<", "CobolCompare.lt(WS-A, 'X')"),
    ],
)
def test_every_operator_spelling(cond, op, java):
    r = one(f"           IF {cond} CONTINUE END-IF.\n")
    assert (r["op"], r["java"]) == (op, java)


def test_an_abbreviated_condition_carries_its_subject_and_operator():
    a, b = facts("           IF WS-A > 'X' AND < 'Y' CONTINUE END-IF.\n")
    assert (a["left"], a["op"], a["right"], a["abbreviated"]) == ("WS-A", ">", "'X'", False)
    assert (b["left"], b["op"], b["right"], b["abbreviated"]) == ("WS-A", "<", "'Y'", True)
    assert b["java"] == "CobolCompare.lt(WS-A, 'Y')"
    a, b, c = facts("           IF WS-A = 'X' OR 'Y' OR NOT 'Z' CONTINUE END-IF.\n")
    assert [(r["op"], r["right"]) for r in (a, b, c)] == [("=", "'X'"), ("=", "'Y'"), ("<>", "'Z'")]
    assert b["abbreviated"] and c["abbreviated"]


def test_numeric_and_alphanumeric_comparisons_are_told_apart():
    rows = facts("           IF WS-N > 5 OR WS-P < WS-N OR WS-E = 1 OR WS-N = ZERO OR WS-N + 1 > 3 CONTINUE END-IF.\n")
    assert [r["kind"] for r in rows] == ["numeric"] * 5 and not any("java" in r for r in rows)
    rows = facts("           IF WS-N = '001' OR WS-G = WS-G1 OR WS-A = ZERO OR WS-A = ALL 'X' CONTINUE END-IF.\n")
    assert [r["kind"] for r in rows] == ["alphanumeric"] * 4  # a numeric item against a literal is a byte compare
    assert rows[1]["left_class"] == "group"
    assert rows[2]["right_class"] == "zero"


def test_figurative_constants_and_hex_literals():
    rows = facts(
        "           IF WS-A = SPACES OR WS-A = LOW-VALUES OR WS-A > HIGH-VALUES OR WS-A = X'00' CONTINUE END-IF.\n"
    )
    assert [r["right_class"] for r in rows] == ["figurative", "figurative", "figurative", "alphanumeric"]
    assert {r["kind"] for r in rows} == {"alphanumeric"}


def test_subscripts_reference_modification_and_qualifiers():
    (r,) = facts("           IF WS-A (IDX) = WS-G1 OF WS-G CONTINUE END-IF.\n")
    assert (r["left"], r["right"], r["kind"]) == ("WS-A(IDX)", "WS-G1 OF WS-G", "alphanumeric")
    (r,) = facts("           IF WS-N(1:2) = 'AB' CONTINUE END-IF.\n")
    assert (r["left"], r["left_class"]) == ("WS-N(1:2)", "alphanumeric")  # a refmod of a numeric item is bytes


def test_class_sign_and_condition_name_tests_are_not_comparisons():
    body = (
        "           IF WS-A IS NUMERIC OR WS-A IS NOT ALPHABETIC OR WS-N IS POSITIVE OR WS-N IS NEGATIVE\n"
        "              OR IS-LETTER OR IS-Y OR NOT IS-Y OR WS-A IS WS-CLASS CONTINUE END-IF.\n"
    )
    assert facts(body) == []


def test_an_unresolved_operand_is_unknown_not_numeric():
    (r,) = facts("           IF MYSTERY > 'A' CONTINUE END-IF.\n")
    assert (r["kind"], r["left_class"]) == ("unknown", "unknown") and "java" not in r
    (r,) = facts("           IF FUNCTION UPPER-CASE(WS-A) = 'AB' CONTINUE END-IF.\n")
    assert r["left_class"] == "alphanumeric" or r["kind"] == "alphanumeric"


def test_a_name_defined_twice_with_different_classes_is_unknown_unless_qualified():
    dup = DATA.replace("PROCEDURE DIVISION.\n", "") + (
        "       01 REC-1.\n          05 CODE-X PIC X.\n       01 REC-2.\n          05 CODE-X PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
    )
    r1, r2 = relation_facts(
        dup + "           IF CODE-X = 'A' OR CODE-X OF REC-1 = 'A' OR CODE-X OF REC-2 = 1 CONTINUE END-IF.\n"
    )[:2]
    assert r1["left_class"] == "unknown"
    assert r2["left_class"] == "alphanumeric"


def test_a_copybook_gives_its_items_their_classes():
    book = "       01 CB-REC.\n          05 CB-NAME PIC X(10).\n          05 CB-AMT PIC 9(5).\n"
    rows = facts("           IF CB-NAME > 'A' OR CB-AMT > 3 CONTINUE END-IF.\n", [book])
    assert [r["kind"] for r in rows] == ["alphanumeric", "numeric"]
    assert facts("           IF CB-NAME > 'A' CONTINUE END-IF.\n")[0]["kind"] == "unknown"


def test_evaluate_when_against_a_subject():
    rows = facts(
        "           EVALUATE WS-A\n              WHEN 'A' THRU 'C' DISPLAY 'x'\n              WHEN 'Q' CONTINUE\n"
        "              WHEN NOT 'Z' CONTINUE\n              WHEN OTHER CONTINUE\n           END-EVALUATE.\n"
    )
    assert [(r["op"], r["right"]) for r in rows] == [(">=", "'A'"), ("<=", "'C'"), ("=", "'Q'"), ("<>", "'Z'")]
    assert {r["context"] for r in rows} == {"EVALUATE WHEN"}
    assert rows[0]["line"] == 20 and rows[2]["line"] == 21


def test_evaluate_true_and_also():
    rows = facts(
        "           EVALUATE TRUE\n              WHEN WS-A > 'M' AND WS-N > 2 CONTINUE\n"
        "              WHEN OTHER CONTINUE\n           END-EVALUATE.\n"
        "           EVALUATE WS-A ALSO WS-N\n              WHEN 'A' ALSO ANY CONTINUE\n"
        "              WHEN 'B' ALSO 3 CONTINUE\n           END-EVALUATE.\n"
    )
    assert [(r["left"], r["op"], r["right"], r["kind"]) for r in rows] == [
        ("WS-A", ">", "'M'", "alphanumeric"),
        ("WS-N", ">", "2", "numeric"),
        ("WS-A", "=", "'A'", "alphanumeric"),
        ("WS-A", "=", "'B'", "alphanumeric"),
        ("WS-N", "=", "3", "numeric"),
    ]


def test_perform_until_and_search_when():
    rows = facts(
        "           PERFORM UNTIL WS-A = 'ZZ' OR WS-N > 9 CONTINUE END-PERFORM.\n"
        "           PERFORM P1 UNTIL WS-A > 'M'.\n"
        "           PERFORM VARYING WS-N FROM 1 BY 1 UNTIL WS-G1 = 'Q' CONTINUE END-PERFORM.\n"
        "           SEARCH ALL TBL WHEN WS-A < WS-B CONTINUE END-SEARCH.\n"
    )
    assert [(r["context"], r["left"], r["kind"]) for r in rows] == [
        ("PERFORM UNTIL", "WS-A", "alphanumeric"),
        ("PERFORM UNTIL", "WS-N", "numeric"),
        ("PERFORM UNTIL", "WS-A", "alphanumeric"),
        ("PERFORM UNTIL", "WS-G1", "alphanumeric"),
        ("SEARCH WHEN", "WS-A", "alphanumeric"),
    ]


def test_exec_blocks_comments_and_data_division_are_skipped():
    body = (
        "           EXEC SQL SELECT A FROM T WHERE B = 'X' END-EXEC.\n"
        "      * IF WS-A > 'X' CONTINUE END-IF.\n"
        "           MOVE 'IF WS-A > B' TO WS-A.\n"
    )
    assert facts(body) == []
    assert relation_facts("") == [] and relation_facts("       PROCEDURE DIVISION.\n           STOP RUN.\n") == []


def test_level_88_ranges_over_non_numeric_items():
    (r,) = condition_ranges(DATA)
    assert (r["name"], r["parent"], r["parent_class"], r["line"]) == ("IS-LETTER", "WS-C", "alphanumeric", 14)
    assert r["ranges"] == [{"lo": "'A'", "hi": "'Z'"}]  # SMALL-K is numeric, IS-Y has no range


def test_collating_sequence_declarations():
    src = (
        "       OBJECT-COMPUTER. X PROGRAM COLLATING SEQUENCE IS ASC.\n"
        "       SPECIAL-NAMES. ALPHABET ASC IS STANDARD-1\n          ALPHABET NAT IS NATIVE.\n"
    )
    rows = collating_sequence(src)
    assert [(r["clause"], r["name"], r["definition"], r["custom"]) for r in rows] == [
        ("PROGRAM COLLATING SEQUENCE", "ASC", "STANDARD-1", True),
        ("ALPHABET", "ASC", "STANDARD-1", True),
        ("ALPHABET", "NAT", "NATIVE", False),
    ]
    assert collating_sequence("       PROCEDURE DIVISION.\n           STOP RUN.\n") == []
    (rule,) = collating_sequence_rules(rows)
    assert "ASC" in rule and "STANDARD-1" in rule and "TODO" in rule
    native = collating_sequence(
        "       OBJECT-COMPUTER. X PROGRAM COLLATING SEQUENCE IS NAT.\n       SPECIAL-NAMES. ALPHABET NAT IS EBCDIC.\n"
    )
    assert collating_sequence_rules(native) == []


def _ticket(tmp_path: Path, source: str):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "T.cbl").write_text(source, encoding="utf-8")
    skeleton = {"program": {"file": "T.cbl", "language": "cobol", "program_ids": ["T"]}, "sections": {}}
    return build_ticket("T", skeleton, tmp_path, "com.acme", tmp_path / "src", None, [], {}, None)


def test_the_ticket_lists_the_comparisons(tmp_path):
    t = _ticket(
        tmp_path,
        DATA + "           IF WS-A > 'X' AND < 'Y' CONTINUE END-IF.\n           IF WS-N > 1 CONTINUE END-IF.\n",
    )
    assert [r["java"] for r in t["relations"]] == ["CobolCompare.gt(WS-A, 'X')", "CobolCompare.lt(WS-A, 'Y')"]
    assert t["condition_ranges"][0]["name"] == "IS-LETTER"
    assert "collating_sequence" not in t
    md = ticket_markdown(t)
    assert "## Alphanumeric relation conditions" in md and "`CobolCompare.lt(WS-A, 'Y')`" in md
    assert "IS-LETTER" in md and "`'A' THRU 'Z'`" in md
    json.dumps(t)


def test_a_program_without_comparisons_adds_no_keys(tmp_path):
    t = _ticket(tmp_path, "       PROCEDURE DIVISION.\n           STOP RUN.\n")
    assert not {"relations", "condition_ranges", "collating_sequence"} & set(t)
    assert "Alphanumeric relation conditions" not in ticket_markdown(t)


def test_a_custom_collating_sequence_reaches_the_ticket(tmp_path):
    src = (
        "       OBJECT-COMPUTER. X PROGRAM COLLATING SEQUENCE IS ASC.\n       SPECIAL-NAMES. ALPHABET ASC IS STANDARD-1.\n"
        + DATA
        + "           IF WS-A > 'X' CONTINUE END-IF.\n"
    )
    t = _ticket(tmp_path, src)
    assert t["collating_sequence"][0]["custom"]
    assert any("PROGRAM COLLATING SEQUENCE IS ASC" in r for r in t["rules"])


BURNED = ("aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp")


@pytest.mark.skipif(not os.environ.get("GITGALAXY_MAINFRAME_CORPORA"), reason="needs the mainframe corpora")
def test_burned_estates_yield_rows_without_crashing():
    root = Path(os.environ["GITGALAXY_MAINFRAME_CORPORA"])
    total = 0
    for name in BURNED:
        for path in sorted((root / name).rglob("*.cbl"))[:40]:
            text = path.read_text(encoding="latin-1")
            for r in relation_facts(text):
                assert r["kind"] in ("alphanumeric", "numeric", "unknown") and r["op"] in (
                    "=",
                    "<>",
                    ">",
                    ">=",
                    "<",
                    "<=",
                )
                total += 1
    assert total > 0
