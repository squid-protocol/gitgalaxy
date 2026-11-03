"""#4175: the branch solver's answers on small programs, one per modelling rule (branch_solver.py)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("z3")
pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import branch_solver as bs


def _program(tmp_path, data: str, proc: str):
    """A fixed-format program: `data` lines go in WORKING-STORAGE, `proc` lines in the PROCEDURE DIVISION."""
    head = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. T.", "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION."]  # fmt: skip
    body = [f"       {x}" for x in data.strip("\n").split("\n")]
    body += ["       LINKAGE SECTION.", "       01 LK-AREA.", "          05 LK-CODE PIC X(2).",
             "          05 LK-N    PIC 9(3).", "       PROCEDURE DIVISION USING LK-AREA."]  # fmt: skip
    body += [f"       {x}" for x in proc.strip("\n").split("\n")]
    src = tmp_path / "T.cbl"
    src.write_text("\n".join(head + body) + "\n", encoding="utf-8")
    prog = bs.load_program(src, [])
    w = bs.Walk(prog, bs.evaluate_arms(src))
    w.explore()
    return w, src


def _line(src: Path, text: str) -> int:
    return next(i for i, x in enumerate(src.read_text().split("\n"), 1) if text in x)


def _verdict(w, line: int, outcome: str) -> str:
    return w.ask(w.hits.get((line, outcome), []))[0]


def test_a_loop_flag_that_only_holds_n_or_y_is_confirmed(tmp_path):
    w, src = _program(
        tmp_path,
        "01 EOF PIC X VALUE 'N'.",
        """
           PERFORM UNTIL EOF = 'Y'
               IF EOF = 'N'
                   IF LK-CODE = 'XX'
                       MOVE 'Y' TO EOF
                   END-IF
               END-IF
           END-PERFORM
           GOBACK.""",
    )
    ln = _line(src, "IF EOF = 'N'")
    assert _verdict(w, ln, "false") == "confirmed"
    assert _verdict(w, ln, "true") == "witness"


def test_an_input_that_reaches_the_outcome_is_a_witness_with_its_value(tmp_path):
    w, src = _program(
        tmp_path,
        "01 X PIC X.",
        """
           IF LK-N > 500
               MOVE 'A' TO X
           END-IF
           GOBACK.""",
    )
    ln = _line(src, "IF LK-N")
    v, model = w.ask(w.hits[(ln, "true")])
    assert v == "witness"
    found = w.witness(model, w.hits[(ln, "true")])
    assert [x["item"] for x in found] == ["LK-N"] and found[0]["value"] > 500


def test_a_flag_another_statement_sets_from_an_input_is_not_confirmed(tmp_path):
    w, src = _program(
        tmp_path,
        "01 EOF PIC X VALUE 'N'.",
        """
           PERFORM UNTIL EOF = 'Y'
               IF EOF = 'N'
                   MOVE LK-CODE TO EOF
               END-IF
           END-PERFORM
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "IF EOF = 'N'"), "false") == "witness"


def test_an_unmodelled_statement_sets_what_it_names_to_any_value(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'N'.",
        """
           CALL 'SUB' USING F
           IF F = 'N'
               CONTINUE
           END-IF
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "IF F = 'N'"), "false") == "witness"


def test_a_constant_88_and_an_evaluate_arm_after_it(tmp_path):
    w, src = _program(
        tmp_path,
        "01 MODE-SW PIC X VALUE 'A'.\n   88 MODE-A VALUE 'A'.\n   88 MODE-B VALUE 'B'.",
        """
           EVALUATE TRUE
               WHEN MODE-A
                   CONTINUE
               WHEN MODE-B
                   CONTINUE
               WHEN OTHER
                   CONTINUE
           END-EVALUATE
           GOBACK.""",
    )
    ln = _line(src, "EVALUATE TRUE")
    arms = bs.evaluate_arms(src)[ln]
    assert _verdict(w, ln, arms[0]) == "witness"
    assert _verdict(w, ln, arms[1]) == "confirmed" and _verdict(w, ln, "OTHER") == "confirmed"


def test_go_to_and_perform_thru_reach_paragraphs(tmp_path):
    w, src = _program(
        tmp_path,
        "01 S PIC 9 VALUE 0.",
        """
       A000.
           PERFORM B000 THRU B999
           IF S = 2
               CONTINUE
           END-IF
           GOBACK.
       B000.
           MOVE 1 TO S
           GO TO B999.
       B500.
           MOVE 3 TO S.
       B999.
           ADD 1 TO S.""",
    )
    ln = _line(src, "IF S = 2")
    # ADD is not modelled exactly: S is any value S can hold (0, 1, 3 from MOVEs; ADD makes it any digit)
    assert _verdict(w, ln, "true") == "witness"
    assert w.ask(w.entered.get("B500", []))[0] == "confirmed"


def test_an_alter_makes_a_confirmation_inconclusive(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'N'.",
        """
       A000.
           ALTER B000 TO PROCEED TO C000
           IF F = 'Y'
               CONTINUE
           END-IF
           GOBACK.
       B000.
           GO TO C000.
       C000.
           GOBACK.""",
    )
    assert w.why and _verdict(w, _line(src, "IF F = 'Y'"), "true") == "inconclusive"


def test_cics_return_ends_the_path_and_handle_labels_are_branches(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'N'.",
        """
       A000.
           EXEC CICS HANDLE CONDITION NOTFND(B000) END-EXEC
           EXEC CICS READ FILE('X') INTO(LK-AREA) END-EXEC
           EXEC CICS RETURN END-EXEC.
       B000.
           IF F = 'N'
               CONTINUE
           END-IF
           EXEC CICS RETURN END-EXEC.""",
    )
    assert _verdict(w, _line(src, "IF F = 'N'"), "true") == "witness"


def test_a_group_condition_name_compares_the_whole_group(tmp_path):
    w, src = _program(
        tmp_path,
        "01 G.\n   88 G-EMPTY VALUE SPACES.\n   05 G1 PIC X(2) VALUE 'AB'.\n   05 G2 PIC X VALUE 'C'.",
        """
           IF G-EMPTY
               CONTINUE
           END-IF
           MOVE SPACES TO G
           IF G-EMPTY
               CONTINUE
           END-IF
           GOBACK.""",
    )
    first, second = [i for i, x in enumerate(src.read_text().split("\n"), 1) if "IF G-EMPTY" in x]
    assert _verdict(w, first, "true") == "confirmed"  # 'ABC' is no group of spaces
    assert _verdict(w, second, "false") == "confirmed"


def test_a_printable_witness_is_preferred(tmp_path):
    w, src = _program(
        tmp_path,
        "01 X PIC X.",
        """
           IF LK-CODE NOT = SPACES AND LK-CODE NOT = 'AA'
               MOVE 'A' TO X
           END-IF
           GOBACK.""",
    )
    ln = _line(src, "IF LK-CODE")
    _, model = w.ask(w.hits[(ln, "true")], printable=True)
    (code,) = [x["value"] for x in w.witness(model, w.hits[(ln, "true")]) if x["item"] == "LK-CODE"]
    assert code.strip() and code != "AA" and all(c.isalnum() or c in " -" for c in code)


def test_a_table_of_constants_read_by_subscript_holds_only_its_values(tmp_path):
    data = (
        "01 T-DATA.\n   05 FILLER PIC X VALUE 'U'.\n   05 FILLER PIC X VALUE 'U'.\n"
        "01 T-TAB REDEFINES T-DATA.\n   05 T-TYPE PIC X OCCURS 2.\n01 I PIC 9 VALUE 1."
    )
    w, src = _program(
        tmp_path,
        data,
        """
           MOVE LK-N TO I
           IF T-TYPE(I) = 'A'
               CONTINUE
           END-IF
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "IF T-TYPE(I)"), "true") == "confirmed"


def test_a_varying_index_stays_in_its_bounds(tmp_path):
    w, src = _program(
        tmp_path,
        "01 IX PIC 99 VALUE 0.",
        """
           PERFORM VARYING IX FROM 1 BY 1 UNTIL IX > 5
               EVALUATE IX
                   WHEN 1 THRU 5
                       CONTINUE
                   WHEN OTHER
                       CONTINUE
               END-EVALUATE
           END-PERFORM
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "EVALUATE IX"), "OTHER") == "confirmed"


def test_a_cics_command_sets_the_eib_but_not_what_it_sends(tmp_path):
    w, src = _program(
        tmp_path,
        "01 MSG PIC X(4) VALUE 'ABCD'.",
        """
           EXEC CICS SEND TEXT FROM(MSG) NOHANDLE END-EXEC
           IF MSG = 'ABCD'
               CONTINUE
           END-IF
           IF EIBRESP = 0
               CONTINUE
           END-IF
           EXEC CICS RETURN END-EXEC.""",
    )
    assert _verdict(w, _line(src, "IF MSG"), "false") == "confirmed"
    assert _verdict(w, _line(src, "IF EIBRESP"), "false") == "witness"


def test_perform_of_a_section_runs_the_whole_section(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'N'.",
        """
       MAIN-S SECTION.
       M010.
           PERFORM EXIT-S.
       M999.
           EXIT.
       TIME-S SECTION.
       T010.
           MOVE 'Y' TO F.
       EXIT-S SECTION.
       X010.
           GOBACK.""",
    )
    assert w.ask(w.entered.get("T010", []))[0] == "confirmed"


def test_a_handler_that_performs_back_into_a_running_range_terminates(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'N'.",
        """
       MAIN-PARA.
           EXEC CICS HANDLE CONDITION PGMIDERR(ERR-PARA) END-EXEC
           PERFORM SEND-SCREEN
           EXEC CICS RETURN END-EXEC.
       SEND-SCREEN.
           EXEC CICS SEND TEXT FROM(F) END-EXEC.
       ERR-PARA.
           MOVE 'Y' TO F
           PERFORM SEND-SCREEN
           IF F = 'Q'
               CONTINUE
           END-IF
           EXEC CICS RETURN END-EXEC.""",
    )
    assert not w.why
    assert _verdict(w, _line(src, "IF F = 'Q'"), "true") == "confirmed"


def test_an_evaluate_without_other_names_its_fall_through_as_coverage_does(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'A'.",
        """
           EVALUATE F
               WHEN 'A'
                   CONTINUE
               WHEN 'B'
                   CONTINUE
           END-EVALUATE
           GOBACK.""",
    )
    ln = _line(src, "EVALUATE F")
    fall = bs.evaluate_arms(src)[ln][-1]
    assert fall != "OTHER" and w.hits.get((ln, fall))
    assert _verdict(w, ln, fall) == "confirmed" and (ln, "NO-SUCH") not in w.known()


def test_set_of_a_group_condition_name_changes_the_group_items(tmp_path):
    w, src = _program(
        tmp_path,
        "01 G.\n   88 G-RESET VALUE 'ZZ'.\n   05 G1 PIC X VALUE 'A'.\n   05 G2 PIC X VALUE 'B'.",
        """
           SET G-RESET TO TRUE
           IF G1 = 'A'
               CONTINUE
           END-IF
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "IF G1"), "false") == "witness"


def test_initialize_leaves_filler_alone(tmp_path):
    w, src = _program(
        tmp_path,
        "01 G.\n   05 FILLER PIC X VALUE 'Q'.\n   05 G1 PIC X VALUE 'A'.",
        """
           INITIALIZE G
           IF G = 'Q '
               CONTINUE
           END-IF
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "IF G ="), "false") == "confirmed"


def test_an_item_whose_address_is_taken_is_not_followed(tmp_path):
    w, src = _program(
        tmp_path,
        "01 F PIC X VALUE 'N'.\n01 P USAGE POINTER.",
        """
           SET P TO ADDRESS OF F
           CALL 'SUB' USING BY VALUE P
           IF F = 'N'
               CONTINUE
           END-IF
           GOBACK.""",
    )
    assert _verdict(w, _line(src, "IF F"), "false") == "witness"


def test_a_resp_arm_gets_a_fault_plan_on_the_command(tmp_path):
    pytest.importorskip("equivalence_cics_faults")
    w, src = _program(
        tmp_path,
        "01 WS-RESP PIC S9(8) COMP.\n01 KEYV PIC X(4) VALUE 'K001'.\n01 REC PIC X(10).",
        """
           EXEC CICS READ FILE('ACCTDAT') INTO(REC) RIDFLD(KEYV)
                RESP(WS-RESP) END-EXEC
           IF WS-RESP = DFHRESP(NOTFND)
               CONTINUE
           END-IF
           EXEC CICS RETURN END-EXEC.""",
    )
    ln = _line(src, "IF WS-RESP")
    f = w.hits[(ln, "true")]
    verdict, model = w.ask(f, printable=True)
    assert verdict == "witness"
    got = bs.scenario(w, model, f, {"kind": "cics"}, f"{ln}:true")
    assert got["faults"] == [{"cmd": "READ", "file": "ACCTDAT", "nth": 1, "resp": "NOTFND", "resp2": 80}]


def test_a_witness_prefers_a_value_the_case_already_uses(tmp_path):
    w, src = _program(
        tmp_path,
        "01 X PIC X.",
        """
           IF LK-CODE NOT = SPACES
               MOVE 'A' TO X
           END-IF
           GOBACK.""",
    )
    w.known_values = {"LK-CODE": {"Q7"}}
    ln = _line(src, "IF LK-CODE")
    _, model = w.ask(w.hits[(ln, "true")], printable=True)
    assert [x["value"] for x in w.witness(model, w.hits[(ln, "true")]) if x["item"] == "LK-CODE"] == ["Q7"]
