"""
#3454: batch CALL USING lists and program entry points (core/call_using.py),
through `extract_boundary`: CardDemo CORPT00C -> CSUTLDTC, zopeneditor SAM1 ->
SAM2, IMS DLITCBL entries, BY CONTENT / BY VALUE, qualified and subscripted
items, and a numbered line's cols 73-80 tag.
"""

from gitgalaxy.core.call_using import entry_points
from gitgalaxy.core.mainframe_boundary import extract_boundary


def _using(src: str) -> list[tuple]:
    return [(c["operand"], c.get("using_args")) for c in extract_boundary("cobol", src)["calls"] if c["verb"] == "CALL"]


def test_call_using_lists():
    src = (
        "           CALL 'CSUTLDTC' USING   CSUTLDTC-DATE\n"
        "                                   CSUTLDTC-DATE-FORMAT\n"
        "                                   CSUTLDTC-RESULT\n"
        "           CALL 'SAM2' USING BY REFERENCE CUST-REC, TRAN-REC\n"
        "                BY CONTENT 'X' WS-FLAG BY VALUE WS-LEN\n"
        "                ON EXCEPTION DISPLAY 'NO SAM2'\n"
        "           END-CALL\n"
        "           CALL WS-PGM USING A OF B, TAB(I), ADDRESS OF P, OMITTED.\n"
        "           CALL 'CEE3ABD'.\n"
        "           MOVE 1 TO X.\n"
    )
    assert _using(src) == [
        ("CSUTLDTC", "CSUTLDTC-DATE,CSUTLDTC-DATE-FORMAT,CSUTLDTC-RESULT"),
        ("SAM2", "CUST-REC,TRAN-REC,CONTENT:'X',CONTENT:WS-FLAG,VALUE:WS-LEN"),
        ("WS-PGM", "A OF B,TAB,ADDRESS OF P,OMITTED"),
        ("CEE3ABD", None),
    ]


def test_an_unterminated_list_stops_at_the_next_verb_and_seq_tags_are_ignored():
    src = (
        "019200     CALL 'MQOPEN' USING QMGR-HANDLE-CONN                         01820012\n"
        "019300                         MQ-OBJECT-DESCRIPTOR                     01830012\n"
        "019400     MOVE MQ-HOBJ TO X                                            01840012\n"
    )
    assert _using(src) == [("MQOPEN", "QMGR-HANDLE-CONN,MQ-OBJECT-DESCRIPTOR")]


def test_entry_points():
    src = (
        "       PROCEDURE DIVISION USING PAUTBPCB PASFLPCB.\n"
        "       MAIN-PARA.\n"
        "           ENTRY 'DLITCBL' USING PAUTBPCB PASFLPCB.\n"
        "           GOBACK.\n"
    )
    assert [(e["kind"], e["entry_name"], e["params"], e["line"]) for e in entry_points(src)] == [
        ("PROCEDURE", None, "PAUTBPCB,PASFLPCB", 1),
        ("ENTRY", "DLITCBL", "PAUTBPCB,PASFLPCB", 3),
    ]
    assert [e["params"] for e in entry_points("       PROCEDURE DIVISION.\n")] == [None]
