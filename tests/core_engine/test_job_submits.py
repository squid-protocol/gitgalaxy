"""
#3448: job-submission evidence (core/job_submits.py), run through
`extract_boundary` exactly as a scan does: the JCL JOB / EXEC cards a COBOL
program holds as literals (CardDemo CORPT00C) and the JCL DDs routed to the
internal reader (CardDemo INTRDRJ1).
"""

import time

from gitgalaxy.core.job_submits import cobol_job_cards
from gitgalaxy.core.mainframe_boundary import extract_boundary

CORPT00C = (
    "       01 JOB-DATA.\n"
    "        02 JOB-DATA-1.\n"
    "         05 FILLER                     PIC X(80) VALUE\n"
    "         \"//TRNRPT00 JOB 'TRAN REPORT',CLASS=A,MSGCLASS=0,\".\n"
    "         05 FILLER                     PIC X(80) VALUE\n"
    '         "//STEP10 EXEC PROC=TRANREPT".\n'
    "         05 FILLER                     PIC X(80) VALUE\n"
    '         "//STEP20 EXEC PGM=IEFBR14".\n'
    "         05 FILLER                     PIC X(80) VALUE\n"
    '         "//STEP30 EXEC SORTPROC".\n'
    '         05 FILLER                     PIC X(80) VALUE "/*EOF".\n'
)


def _rows(source: str, dialect: str) -> list[tuple]:
    return [
        (r["kind"], r["step"], r["name"], r["target_kind"], r["target"])
        for r in extract_boundary(dialect, source)["job_submits"]
    ]


def test_cobol_job_and_exec_card_literals():
    assert _rows(CORPT00C, "cobol") == [
        ("JOB", None, "TRNRPT00", None, None),
        ("EXEC", "STEP10", None, "PROC", "TRANREPT"),
        ("EXEC", "STEP20", None, "PGM", "IEFBR14"),
        ("EXEC", "STEP30", None, "PROC", "SORTPROC"),
    ]


def test_exec_cards_without_a_job_card_are_not_jcl():
    src = "           DISPLAY '//STEP1 EXEC PGM=X'.\n           MOVE '// EXEC Y' TO WS-A.\n"
    assert _rows(src, "cobol") == []


def test_a_quote_inside_another_literal_is_not_an_opening_quote():
    src = '           DISPLAY "IT\'S //NOTAJOB JOB".\n'
    assert _rows(src, "cobol") == []


def test_jcl_intrdr_dd_takes_the_steps_sysut1_member():
    src = (
        "//INTRDRJ1 JOB (COBOL),'KSSOMAS',CLASS=A\n"
        "//STEP01 EXEC PGM=IEBGENER\n"
        "//SYSPRINT DD SYSOUT=*\n"
        "//SYSUT1 DD DSN=AWS.M2.CARDDEMO.JCL(INTRDRJ2),DISP=SHR\n"
        "//SYSUT2 DD SYSOUT=(A,INTRDR),DCB=(LRECL=80,BLKSIZE=80)\n"
        "//STEP02 EXEC PGM=IEBGENER\n"
        "//SYSUT2 DD SYSOUT=(*,INTRDR)\n"
        "//REPORT DD SYSOUT=A\n"
    )
    assert _rows(src, "jcl") == [
        ("INTRDR", "STEP01", "SYSUT2", "DSN", "AWS.M2.CARDDEMO.JCL(INTRDRJ2)"),
        ("INTRDR", "STEP02", "SYSUT2", None, None),
    ]


def test_a_cics_region_intrdr_dd_is_found_too():
    src = "//CICSRUN EXEC PGM=DFHSIP\n//INREADER DD SYSOUT=(A,INTRDR)\n"
    assert _rows(src, "jcl") == [("INTRDR", "CICSRUN", "INREADER", None, None)]


def test_the_card_scan_is_bounded():
    src = ("           MOVE '//" + "A" * 5000 + " JOB' TO X.\n") * 200 + "'//" * 20000
    started = time.perf_counter()
    cobol_job_cards(src)
    assert time.perf_counter() - started < 5.0
