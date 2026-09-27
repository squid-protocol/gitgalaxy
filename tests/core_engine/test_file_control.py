"""
#3455: file definitions (core/file_control.py), through `extract_boundary`:
FILE-CONTROL SELECT clauses (CardDemo CBTRN02C / CBACT04C shapes) with the FD's
COPY members, and IDCAMS DEFINE CLUSTER / AIX / PATH in JCL in-stream data
(CardDemo XREFFILE.jcl, ESDSRRDS.jcl).
"""

import time

from gitgalaxy.core.file_control import cobol_file_control, jcl_vsam_defines
from gitgalaxy.core.mainframe_boundary import extract_boundary

PROGRAM = (
    "       ENVIRONMENT DIVISION.\n"
    "       INPUT-OUTPUT SECTION.\n"
    "       FILE-CONTROL.\n"
    "           SELECT XREF-FILE ASSIGN TO   XREFFILE\n"
    "                  ORGANIZATION IS INDEXED\n"
    "                  ACCESS MODE  IS DYNAMIC\n"
    "                  RECORD KEY   IS FD-XREF-CARD-NUM\n"
    "                  ALTERNATE RECORD KEY IS FD-XREF-ACCT-ID\n"
    "                     WITH DUPLICATES\n"
    "                  FILE STATUS  IS XREFFILE-STATUS.\n"
    "           SELECT OPTIONAL RPT-FILE ASSIGN TO 'RPTOUT'\n"
    "                  ORGANIZATION IS LINE SEQUENTIAL.\n"
    "           SELECT REL-FILE ASSIGN TO RELDD\n"
    "                  RELATIVE ACCESS IS RANDOM\n"
    "                  RELATIVE KEY IS WS-RRN.\n"
    "       DATA DIVISION.\n"
    "       FILE SECTION.\n"
    "       FD  XREF-FILE.\n"
    "       COPY CVACT03Y.\n"
    "       FD  RPT-FILE.\n"
    "       01  RPT-REC PIC X(80).\n"
    "       WORKING-STORAGE SECTION.\n"
    "       COPY CVEXPORT.\n"
)


def test_select_clauses_and_fd_copies():
    rows = extract_boundary("cobol", PROGRAM)["file_control"]
    got = [
        (
            r["select_name"],
            r["assign"],
            r["organization"],
            r["access_mode"],
            r["record_key"],
            r["alternate_keys"],
            r["relative_key"],
            r["file_status"],
            r["fd_copies"],
            r["line"],
        )
        for r in rows
    ]
    assert got == [
        (
            "XREF-FILE",
            "XREFFILE",
            "INDEXED",
            "DYNAMIC",
            "FD-XREF-CARD-NUM",
            "FD-XREF-ACCT-ID+DUP",
            None,
            "XREFFILE-STATUS",
            "CVACT03Y",
            4,
        ),
        # The WORKING-STORAGE COPY is not the FD's.
        ("RPT-FILE", "RPTOUT", "LINE SEQUENTIAL", None, None, None, None, None, None, 11),
        ("REL-FILE", "RELDD", "RELATIVE", "RANDOM", None, None, "WS-RRN", None, None, 13),
    ]


def test_no_file_control_draws_nothing():
    assert extract_boundary("cobol", "       PROCEDURE DIVISION.\n           GOBACK.\n")["file_control"] == []


JCL = """\
//XREFFILE JOB 'X',CLASS=A
//STEP10  EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE CLUSTER (NAME(AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS)    -
          CYLINDERS(1 5)                                       -
          KEYS(16 0)                                           -
          RECORDSIZE(50 50)                                    -
          SHAREOPTIONS(2 3)                                    -
          ERASE                                                -
          INDEXED                                              -
          )                                                    -
          DATA (NAME(AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS.DATA)) -
          INDEX (NAME(AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS.INDEX))
/*
//STEP20  EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE ALTERNATEINDEX (NAME(AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX) -
   RELATE(AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS)                   -
   KEYS(11 25)                                                  -
   NONUNIQUEKEY                                                 -
   UPGRADE                                                      -
   RECORDSIZE(50 50))
   DEF PATH (NAME(AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX.PATH) -
     PENT(AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX))
   DEFINE CLUSTER (NAME(AWS.M2.CARDDEMO.USRSEC.VSAM.RRDS) /* RRDS */ -
          NUMBERED RECSZ(80 80))
   DEFINE GDG (NAME(AWS.M2.CARDDEMO.TRANSACT.BKUP) LIMIT(5))
/*
"""


def test_idcams_cluster_aix_path():
    rows = extract_boundary("jcl", JCL)["vsam_defines"]
    got = [
        (
            r["kind"],
            r["name"],
            r["organization"],
            r["key_length"],
            r["key_offset"],
            r["record_max"],
            r["related"],
            r["unique_key"],
            r["upgrade"],
            r["step"],
            r["line"],
        )
        for r in rows
    ]
    assert got == [
        ("CLUSTER", "AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS", "INDEXED", 16, 0, 50, None, None, None, "STEP10", 4),
        (
            "AIX",
            "AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX",
            None,
            11,
            25,
            50,
            "AWS.M2.CARDDEMO.CARDXREF.VSAM.KSDS",
            "NONUNIQUE",
            "UPGRADE",
            "STEP20",
            17,
        ),
        (
            "PATH",
            "AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX.PATH",
            None,
            None,
            None,
            None,
            "AWS.M2.CARDDEMO.CARDXREF.VSAM.AIX",
            None,
            None,
            "STEP20",
            23,
        ),
        ("CLUSTER", "AWS.M2.CARDDEMO.USRSEC.VSAM.RRDS", "NUMBERED", None, None, 80, None, None, None, "STEP20", 25),
    ]


def test_the_scans_are_bounded():
    src = "       FILE-CONTROL.\n" + "           SELECT A ASSIGN TO B " * 5000 + "\n"
    jcl = "   DEFINE CLUSTER (NAME(X) -\n" * 5000
    started = time.perf_counter()
    cobol_file_control(src)
    jcl_vsam_defines(jcl)
    assert time.perf_counter() - started < 5.0


def test_sequential_synonyms():
    """#3898: ORGANIZATION is optional, so a bare `LINE SEQUENTIAL` is LINE SEQUENTIAL, not SEQUENTIAL;
    Micro Focus `RECORD SEQUENTIAL` is SEQUENTIAL; RECORD KEY / ALTERNATE RECORD KEY are untouched."""
    PROGRAM_SEQ = (
        "       FILE-CONTROL.\n"
        "           SELECT BARE-LINE-SEQ ASSIGN TO '1.txt' LINE SEQUENTIAL.\n"
        "           SELECT ORG-LINE-SEQ ASSIGN TO '2.txt' ORGANIZATION LINE SEQUENTIAL.\n"
        "           SELECT ORG-IS-LINE-SEQ ASSIGN TO '3.txt' ORGANIZATION IS LINE SEQUENTIAL.\n"
        "           SELECT BARE-REC-SEQ ASSIGN TO '4.txt' RECORD SEQUENTIAL.\n"
        "           SELECT ORG-IS-REC-SEQ ASSIGN TO '5.txt' ORGANIZATION IS RECORD SEQUENTIAL.\n"
        "           SELECT PLAIN-SEQ ASSIGN TO '6.txt' SEQUENTIAL.\n"
        "           SELECT IDX-FILE ASSIGN TO '7.txt'\n"
        "                  ORGANIZATION IS INDEXED\n"
        "                  RECORD KEY IS WS-REC-KEY\n"
        "                  ALTERNATE RECORD KEY IS WS-ALT-KEY WITH DUPLICATES.\n"
    )
    rows = extract_boundary("cobol", PROGRAM_SEQ)["file_control"]
    got = [(r["select_name"], r["organization"]) for r in rows]
    assert got == [
        ("BARE-LINE-SEQ", "LINE SEQUENTIAL"),
        ("ORG-LINE-SEQ", "LINE SEQUENTIAL"),
        ("ORG-IS-LINE-SEQ", "LINE SEQUENTIAL"),
        ("BARE-REC-SEQ", "SEQUENTIAL"),
        ("ORG-IS-REC-SEQ", "SEQUENTIAL"),
        ("PLAIN-SEQ", "SEQUENTIAL"),
        ("IDX-FILE", "INDEXED"),
    ]
    idx_row = rows[-1]
    assert idx_row["record_key"] == "WS-REC-KEY"
    assert idx_row["alternate_keys"] == "WS-ALT-KEY+DUP"
