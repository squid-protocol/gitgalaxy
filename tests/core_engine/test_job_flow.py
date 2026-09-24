"""
#3451: JCL job flow (core/job_flow.py), through `extract_boundary`: steps in
order with COND= and IF / ELSE conditions, PROC calls and in-stream PROCs, a
proc-step override DD (`//PRC001.FILEIN`), concatenations, and each DSN DD's
DISP and GDG generation (CardDemo TRANBKP / COMBTRAN shapes).
"""

import time

from gitgalaxy.core.job_flow import jcl_job_flow
from gitgalaxy.core.mainframe_boundary import extract_boundary

JCL = """\
//COMBTRAN JOB 'COMBINE',CLASS=A,COND=(8,LT)
//BACKUP   PROC
//BK1      EXEC PGM=IDCAMS
//OUT      DD DSN=APP.TRAN.BKUP(+1),DISP=(NEW,CATLG,DELETE)
//         PEND
//STEP05R  EXEC PROC=REPROC,
//            CNTLLIB=AWS.M2.CARDDEMO.CNTL
//PRC001.FILEIN  DD DISP=SHR,
//         DSN=APP.TRAN.KSDS
//STEP10   EXEC PGM=SORT,COND=(4,LT)
//SORTIN   DD DSN=APP.TRAN.BKUP(0),DISP=SHR
//         DD DSN=APP.SYSTRAN(0),DISP=SHR
//SORTOUT  DD DSN=APP.TRAN.COMBINED(+1),
//            DISP=(,CATLG,DELETE)
//SYSOUT   DD SYSOUT=*
//  IF (STEP10.RC = 0) THEN
//STEP20   EXEC PGM=IDCAMS
//IN       DD DSN=APP.TRAN.COMBINED(+1)
//  ELSE
//STEP25   EXEC BACKUP
//  ENDIF
//STEP30   EXEC PGM=IEFBR14
//DEL      DD DSN=APP.OLD,DISP=(MOD,DELETE)
"""


def _rows(kind: str) -> list[tuple]:
    rows = [r for r in extract_boundary("jcl", JCL)["job_flow"] if r["kind"] == kind]
    if kind == "STEP":
        return [
            (r["step_ordinal"], r["step_name"], r["program"], r["proc"], r["cond"], r["if_cond"], r["in_proc"])
            for r in rows
        ]
    if kind == "DD":
        return [(r["step_name"], r["dd_name"], r["dsn"], r["disp"], r["generation"], r["in_proc"]) for r in rows]
    return [(r["name"], r["cond"]) for r in rows]


def test_job_and_steps_in_order_with_conditions():
    assert _rows("JOB") == [("COMBTRAN", "(8,LT)")]
    assert _rows("STEP") == [
        (1, "BK1", "IDCAMS", None, None, None, "BACKUP"),
        (1, "STEP05R", None, "REPROC", None, None, None),
        (2, "STEP10", "SORT", None, "(4,LT)", None, None),
        (3, "STEP20", "IDCAMS", None, None, "(STEP10.RC = 0)", None),
        (4, "STEP25", None, "BACKUP", None, "NOT (STEP10.RC = 0)", None),
        (5, "STEP30", "IEFBR14", None, None, None, None),
    ]


def test_dd_dispositions_generations_overrides_and_concatenation():
    assert _rows("DD") == [
        ("BK1", "OUT", "APP.TRAN.BKUP", "NEW", "+1", "BACKUP"),
        ("PRC001", "FILEIN", "APP.TRAN.KSDS", "SHR", None, None),
        ("STEP10", "SORTIN", "APP.TRAN.BKUP", "SHR", "0", None),
        ("STEP10", "SORTIN", "APP.SYSTRAN", "SHR", "0", None),
        ("STEP10", "SORTOUT", "APP.TRAN.COMBINED", "NEW", "+1", None),
        # No DISP with a DSN is NEW; SYSOUT DDs are not rows.
        ("STEP20", "IN", "APP.TRAN.COMBINED", "NEW", "+1", None),
        ("STEP30", "DEL", "APP.OLD", "MOD", None, None),
    ]


def test_non_jcl_and_bounded():
    assert jcl_job_flow("just text\n") == []
    src = "//S1 EXEC PGM=X,\n" + "//  A=B,\n" * 20000 + "//  C=D\n"
    started = time.perf_counter()
    jcl_job_flow(src)
    assert time.perf_counter() - started < 5.0


def test_a_comment_inside_a_continued_statement_does_not_end_it():
    # CardDemo samples/proc/BUILDONL.prc: the DISP follows two commented-out lines.
    src = (
        "//LKED    EXEC PGM=IEWL\n"
        "//SYSLMOD  DD DSN=&LOADLIB(&MEM),\n"
        "//*           DISP=(OLD,KEEP),SPACE=(CYL,(10,20,10)),\n"
        "//*           UNIT=3390,DSNTYPE=LIBRARY\n"
        "//            DISP=SHR\n"
    )
    ((dd,),) = [[r for r in jcl_job_flow(src) if r["kind"] == "DD"]]
    assert (dd["dsn"], dd["disp"]) == ("&LOADLIB(&MEM)", "SHR")
    # PRISM blanks a comment line to an empty one: same reading.
    blanked = src.replace("//*           DISP=(OLD,KEEP),SPACE=(CYL,(10,20,10)),", "").replace(
        "//*           UNIT=3390,DSNTYPE=LIBRARY", ""
    )
    assert [r["disp"] for r in jcl_job_flow(blanked) if r["kind"] == "DD"] == ["SHR"]
