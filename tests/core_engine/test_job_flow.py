"""
#3451: JCL job flow (core/job_flow.py), through `extract_boundary`: steps in
order with COND= and IF / ELSE conditions, PROC calls and in-stream PROCs, a
proc-step override DD (`//PRC001.FILEIN`), concatenations, and each DSN DD's
DISP and GDG generation (CardDemo TRANBKP / COMBTRAN shapes).
"""

from _timing import assert_cpu_below

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
        # No DISP with a DSN is NEW; SYSOUT and DUMMY DDs are their own row kinds (#7065).
        ("STEP20", "IN", "APP.TRAN.COMBINED", "NEW", "+1", None),
        ("STEP30", "DEL", "APP.OLD", "MOD", None, None),
    ]


def test_non_jcl_and_bounded():
    assert jcl_job_flow("just text\n") == []
    src = "//S1 EXEC PGM=X,\n" + "//  A=B,\n" * 20000 + "//  C=D\n"
    # CPU time, best of 3 (#4477): ms honest, a rescan per continuation is many seconds
    assert_cpu_below(lambda: jcl_job_flow(src), 5.0, what="jcl job flow")


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


def test_an_unnamed_dd_continues_the_step_of_the_dd_it_concatenates_onto():
    # #5218: a continuation of a qualified override DD belongs to the overridden step, not the EXEC step.
    src = (
        "//J JOB\n"
        "//S1 EXEC PROC=P\n"
        "//A.SYSIN DD DSN=X.LIB(M1),DISP=SHR\n"
        "//        DD DSN=X.LIB(M2),DISP=SHR\n"
        "//        DD DSN=X.LIB(M3),DISP=SHR\n"
        "//B.C.SYSIN DD DSN=X.LIB(M4),DISP=SHR\n"
        "//        DD DSN=X.LIB(M5),DISP=SHR\n"
        "//SYSIN DD DSN=X.LIB(M6),DISP=SHR\n"
        "//        DD DSN=X.LIB(M7),DISP=SHR\n"
        "//S2 EXEC PGM=X\n"
        "//        DD DSN=X.LIB(M8),DISP=SHR\n"
        "//SYSIN DD DSN=X.LIB(M9),DISP=SHR\n"
        "//        DD DSN=X.LIB(MA),DISP=SHR\n"
    )
    got = [(r["step_name"], r["dd_name"], r["dsn"]) for r in jcl_job_flow(src) if r["kind"] == "DD"]
    assert got == [
        ("A", "SYSIN", "X.LIB(M1)"),
        ("A", "SYSIN", "X.LIB(M2)"),
        ("A", "SYSIN", "X.LIB(M3)"),
        ("B", "C.SYSIN", "X.LIB(M4)"),
        ("B", "C.SYSIN", "X.LIB(M5)"),
        ("S1", "SYSIN", "X.LIB(M6)"),
        ("S1", "SYSIN", "X.LIB(M7)"),
        ("S2", None, "X.LIB(M8)"),  # nothing above it in this step: no ddname to inherit
        ("S2", "SYSIN", "X.LIB(M9)"),
        ("S2", "SYSIN", "X.LIB(MA)"),
    ]


def test_dsn_nullfile_is_a_dummy_dd_not_a_dataset():
    # z/OS MVS JCL Reference, DSNAME: NULLFILE "has the same effect as coding the DD DUMMY parameter" (H-0084).
    src = (
        "//J JOB\n"
        "//S1 EXEC PGM=SORT\n"
        "//SORTWK01 DD DSN=NULLFILE\n"
        "//SORTWK02 DD DSNAME=nullfile,DISP=SHR\n"
        "//SORTWK03 DD DISP=SHR,\n"
        "//            DSN=NULLFILE\n"
        "//SORTIN DD DSN=NULLFILE.REAL,DISP=SHR\n"
        "//        DD DSN=NULLFILES,DISP=SHR\n"
        "//SORTOUT DD DSN=APP.OUT,DISP=(NEW,CATLG)\n"
    )
    got = [(r["dd_name"], r["dsn"]) for r in jcl_job_flow(src) if r["kind"] == "DD"]
    assert got == [("SORTIN", "NULLFILE.REAL"), ("SORTIN", "NULLFILES"), ("SORTOUT", "APP.OUT")]


def test_dsn_nullfile_is_no_dependency_capture():
    from gitgalaxy.standards.language_standards.languages.jcl import DEFINITION as d

    rx = d["_dependency_capture"] if "_dependency_capture" in d else d["rules"]["_dependency_capture"]
    src = (
        "//A DD DSN=NULLFILE\n//B DD DSNAME=NULLFILE,DISP=SHR\n//C DD DISP=SHR,DSN=NULLFILE\n"
        "//D DD DSN=NULLFILE.X,DISP=SHR\n//E DD DSN=PROD.IN,DISP=SHR\n"
    )
    got = [next(g for g in m.groups() if g) for m in rx.finditer(src)]
    assert got == ["NULLFILE.X", "PROD.IN"]


_NO_DSN_JCL = """\
//J        JOB 1
//P        PROC
//PS       EXEC PGM=X
//PRPT     DD SYSOUT=(B,,STD)
//         PEND
//S1       EXEC PGM=SORT
//SYSOUT   DD SYSOUT=*
//SYSPRINT DD SYSOUT=A,
//            DCB=(RECFM=FBA)
//TRACE    DD DUMMY
//NULL     DD DSN=NULLFILE,DISP=SHR
//DUMDCB   DD DUMMY,DCB=(LRECL=80)
//BARE     DD SYSOUT=(,)
//DATA     DD DSN=A.B,DISP=SHR
//         DD DUMMY
//S2       EXEC P
//P.PRPT   DD SYSOUT=C
//STREAM   DD *
data
/*
"""


def _no_dsn_rows():
    rows = [r for r in jcl_job_flow(_NO_DSN_JCL) if r["kind"] in ("SYSOUT", "DUMMY", "DD")]
    return [(r["kind"], r["step_name"], r["dd_name"], r.get("sysout"), r["in_proc"]) for r in rows]


def test_a_sysout_or_dummy_dd_is_its_own_row_kind_with_the_class_when_coded():
    assert _no_dsn_rows() == [
        ("SYSOUT", "PS", "PRPT", "B", "P"),
        ("SYSOUT", "S1", "SYSOUT", "*", None),
        ("SYSOUT", "S1", "SYSPRINT", "A", None),
        ("DUMMY", "S1", "TRACE", None, None),
        ("DUMMY", "S1", "NULL", None, None),
        ("DUMMY", "S1", "DUMDCB", None, None),
        ("SYSOUT", "S1", "BARE", None, None),
        ("DD", "S1", "DATA", None, None),
        ("DUMMY", "S1", "DATA", None, None),  # an unnamed DD concatenates onto the DD above it
        ("SYSOUT", "P", "PRPT", "C", None),  # an override of the proc step's DD: named after the proc step
    ]


def test_a_sysout_or_dummy_row_has_no_dsn_so_the_dataset_readers_skip_it():
    rows = [r for r in jcl_job_flow(_NO_DSN_JCL) if r["kind"] in ("SYSOUT", "DUMMY")]
    assert rows and all(r["dsn"] is None and r["disp"] is None for r in rows)
    assert [r["dsn"] for r in jcl_job_flow(_NO_DSN_JCL) if r["kind"] == "DD"] == ["A.B"]
    # the sysout key is present only when a class is coded
    assert all(("sysout" in r) == (r["kind"] == "SYSOUT" and r["dd_name"] != "BARE") for r in rows)


def _flow(jcl: str, kind: str) -> list[dict]:
    return [r for r in jcl_job_flow(jcl) if r["kind"] == kind]


def test_job_restart_step_and_checkid_are_kept_on_the_job_row():
    both = _flow("//J JOB (A),'X',RESTART=(CHK020,C0000012),CLASS=A\n//S EXEC PGM=X\n", "JOB")[0]
    assert (both["restart"], both["restart_checkid"]) == ("CHK020", "C0000012")
    bare = _flow("//J JOB (A),'X',RESTART=load020,CLASS=A\n//S EXEC PGM=X\n", "JOB")[0]
    assert bare["restart"] == "LOAD020" and "restart_checkid" not in bare
    star = _flow("//J JOB (A),'X',RESTART=*\n//S EXEC PGM=X\n", "JOB")[0]
    assert star["restart"] == "*"
    none = _flow("//J JOB (A),'X',CLASS=A\n//S EXEC PGM=X\n", "JOB")[0]
    assert "restart" not in none and "restart_checkid" not in none


def test_exec_rd_is_kept_for_every_value_and_absent_otherwise():
    for rd in ("R", "RNC", "NR", "NC"):
        step = _flow(f"//J JOB (A)\n//S EXEC PGM=X,RD={rd}\n", "STEP")[0]
        assert step["rd"] == rd
    assert "rd" not in _flow("//J JOB (A)\n//S EXEC PGM=X\n", "STEP")[0]


def test_proc_step_parm_and_cond_overrides_keep_coded_order_and_quoting():
    jcl = (
        "//J JOB (A)\n"
        "//QTR EXEC BDLDPRC,RPT=DAILY,PARM.RPT020='QUARTERLY',\n"
        "//     COND.RPT020=(4,LT,SRT010),PARM.A='IT''S',COND.B=(0,NE)\n"
    )
    step = _flow(jcl, "STEP")[0]
    assert step["parm_overrides"] == [{"step": "RPT020", "parm": "QUARTERLY"}, {"step": "A", "parm": "IT'S"}]
    assert step["cond_overrides"] == [{"step": "RPT020", "cond": "(4,LT,SRT010)"}, {"step": "B", "cond": "(0,NE)"}]
    assert step["proc"] == "BDLDPRC" and "parm" not in step or step["parm"] is None


def test_a_plain_step_keeps_its_old_shape_without_the_new_keys():
    step = _flow("//J JOB (A)\n//S EXEC PGM=X,PARM='Y',COND=(4,LT)\n", "STEP")[0]
    assert not {"rd", "parm_overrides", "cond_overrides"} & step.keys()


def test_set_keeps_one_row_per_symbol_and_include_keeps_its_member():
    jcl = (
        "//J JOB (A)\n"
        "// SET HLQ=PROD,MSG='A,B',\n"
        "//     Q='IT''S'\n"
        "//S1 EXEC PGM=X\n"
        "// INCLUDE MEMBER=bdldds\n"
        "//P PROC\n"
        "// SET LOCAL=1\n"
        "//PS EXEC PGM=Y\n"
        "// INCLUDE MEMBER=INPROC\n"
        "// PEND\n"
    )
    sets = [(r["name"], r["parm"], r["in_proc"]) for r in _flow(jcl, "SET")]
    assert sets == [("HLQ", "PROD", None), ("MSG", "A,B", None), ("Q", "IT'S", None), ("LOCAL", "1", "P")]
    inc = [(r["name"], r["step_name"], r["in_proc"]) for r in _flow(jcl, "INCLUDE")]
    assert inc == [("BDLDDS", "S1", None), ("INPROC", "PS", "P")]
    assert [r["kind"] for r in jcl_job_flow(jcl)].count("STEP") == 2


def test_a_job_without_set_or_include_has_no_such_rows_and_a_memberless_include_is_dropped():
    assert not {"SET", "INCLUDE"} & {r["kind"] for r in jcl_job_flow("//J JOB (A)\n//S EXEC PGM=X\n")}
    assert _flow("//J JOB (A)\n// INCLUDE\n//S EXEC PGM=X\n", "INCLUDE") == []


def test_output_statements_are_rows_with_their_step_and_keyword_names():
    jcl = (
        "//J JOB (A)\n"
        "//OUT1 OUTPUT DEST=RMT1,CLASS=A,\n"
        "//     COPIES=2\n"
        "//S1 EXEC PGM=X\n"
        "//LOCAL OUTPUT COPIES=3\n"
        "//BARE OUTPUT\n"
        "//P PROC\n"
        "//INP OUTPUT FORMS=STD\n"
        "//PS EXEC PGM=Y\n"
        "// PEND\n"
    )
    got = [(r["name"], r["step_name"], r["in_proc"], r.get("output_params")) for r in _flow(jcl, "OUTPUT")]
    assert got == [
        ("OUT1", None, None, ["DEST", "CLASS", "COPIES"]),
        ("LOCAL", "S1", None, ["COPIES"]),
        ("BARE", "S1", None, None),
        ("INP", None, "P", ["FORMS"]),
    ]
    assert not {"OUTPUT"} & {r["kind"] for r in jcl_job_flow("//J JOB (A)\n//S EXEC PGM=X\n")}


def test_a_sysout_dd_keeps_its_output_references_in_every_form():
    jcl = (
        "//J JOB (A)\n"
        "//S EXEC PGM=X\n"
        "//A DD SYSOUT=*,OUTPUT=*.OUT1\n"
        "//B DD SYSOUT=A,OUTPUT=(*.OUT1,*.S.LOCAL)\n"
        "//C DD SYSOUT=(A,,STD),\n"
        "//     OUTPUT=(OUT2)\n"
        "//D DD SYSOUT=*\n"
    )
    got = {r["dd_name"]: r.get("output_refs") for r in _flow(jcl, "SYSOUT")}
    assert got == {"A": ["*.OUT1"], "B": ["*.OUT1", "*.S.LOCAL"], "C": ["OUT2"], "D": None}


def _parm_of(operand: str) -> str | None:
    return _flow(f"//J JOB (A)\n//S EXEC PGM=X,PARM={operand}\n", "STEP")[0]["parm"]


def test_exec_parm_reads_every_form_of_the_operand_one_element_at_a_time():
    """A sublist's elements are each unquoted; a comma inside apostrophes stays; a quoted string is not a sublist."""
    cases = {
        "ABC": "ABC",
        "'A,B'": "A,B",
        "(A,B)": "A,B",
        "('A','B')": "A,B",
        "('A,1','B')": "A,1,B",
        "('IT''S')": "IT'S",
        "(A,'B C')": "A,B C",
        "('A')": "A",
        "'(AA,BB)'": "(AA,BB)",
        "'&RPT,2'": "&RPT,2",
        "": "",
    }
    for operand, want in cases.items():
        assert _parm_of(operand) == want, operand


def test_a_continued_quoted_parm_and_a_proc_step_parm_override_use_the_same_reading():
    jcl = "//J JOB (A)\n//S EXEC PGM=X,PARM='AAA,BBB,\n//             CCC'\n"
    assert _flow(jcl, "STEP")[0]["parm"] == "AAA,BBB,CCC"
    step = _flow("//J JOB (A)\n//S EXEC P,PARM.A=('X','Y Z'),PARM.B=(Q,R)\n", "STEP")[0]
    assert step["parm_overrides"] == [{"step": "A", "parm": "X,Y Z"}, {"step": "B", "parm": "Q,R"}]


def test_a_set_value_is_not_read_as_a_sublist():
    sets = _flow("//J JOB (A)\n// SET P=(A,B),Q='(C)'\n//S EXEC PGM=X\n", "SET")
    assert [(r["name"], r["parm"]) for r in sets] == [("P", "(A,B)"), ("Q", "(C)")]
