"""JCL oracle for the keyword-family validity tool (#8863): an EXEC step is the function, read through job_flow's statement reader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import family_oracle as fo  # noqa: E402
import family_oracle_jcl  # noqa: E402

ORACLE = family_oracle_jcl.get_oracle()


def _steps(jcl: str) -> dict:
    return {k: v for k, v in ORACLE.index(jcl).items() if k[0] == k[0].upper()}


def _count(jcl: str, name: str = "S1") -> dict:
    steps = ORACLE.index(jcl)
    node = next(v for (n, _), v in steps.items() if n == name)
    return dict(ORACLE.count(node)[0])


def test_registered_under_jcl():
    assert fo.get_oracle("jcl") is ORACLE
    assert ".jcl" in ORACLE.exts


def test_a_step_spans_to_the_next_exec_and_continuations_join():
    jcl = "//J JOB\n//S1 EXEC PGM=A,\n//   PARM='X,Y'\n//D1 DD DSN=A.B,DISP=SHR\n//S2 EXEC PGM=B\n//D2 DD SYSOUT=*\n"
    assert _count(jcl, "S1") == {"args": 1, "io": 1}
    assert _count(jcl, "S2") == {"io": 1}


def test_an_unnamed_exec_is_indexed_under_the_empty_name():
    idx = ORACLE.index("//J JOB\n// EXEC PGM=A,PARM=Z\n")
    assert ("", 2) in idx


def test_comment_lines_and_instream_data_count_nothing():
    jcl = "//S1 EXEC PGM=SORT\n//* //X DD DSN=A,DISP=OLD\n//SYSIN DD *\n DISP=OLD COND=(0,NE) PARM=1\n/*\n"
    assert _count(jcl) == {}


def test_if_is_one_branch_and_else_is_not():
    jcl = "//S1 EXEC PGM=A\n// IF RC=0 THEN\n//S2 EXEC PGM=B\n// ELSE\n//S3 EXEC PGM=C\n// ENDIF\n"
    assert _count(jcl, "S1") == {"branch": 1}
    assert _count(jcl, "S3") == {}


def test_io_skips_temporaries_and_counts_a_dd_once():
    jcl = "//S1 EXEC PGM=A\n//T DD DSN=&&TMP,DISP=(NEW,PASS)\n//D DD DSN=A.B,\n//  DISP=SHR\n//         DD DSNAME=C.D,DISP=SHR\n"
    assert _count(jcl)["io"] == 2


def test_disp_forms():
    jcl = "//S1 EXEC PGM=A\n//A DD DSN=X,DISP=OLD\n//B DD DSN=Y,DISP=(MOD,KEEP)\n//C DD DSN=Z,DISP=(NEW,DELETE)\n//D DD DSN=W,DISP=(OLD,DELETE,KEEP)\n"
    n = _count(jcl)
    assert n["locks"] == 3 and n["cleanup"] == 2


def test_cond_even_and_only_are_not_tests_but_a_combined_form_is():
    assert _count("//S1 EXEC PGM=A,COND=EVEN\n") == {}
    assert _count("//S1 EXEC PGM=A,COND=ONLY\n") == {}
    assert _count("//S1 EXEC PGM=A,COND=(4,LT)\n") == {"safety": 1}
    assert _count("//S1 EXEC PGM=A,COND=((4,LT),EVEN)\n") == {"safety": 1}


def test_danger_names_the_command_runners_only():
    assert _count("//S1 EXEC PGM=IKJEFT01\n") == {"danger": 1}
    assert _count("//S1 EXEC PGM=IEFBR14\n") == {}


def test_a_proc_ends_the_step_and_a_source_without_steps_indexes_to_nothing():
    jcl = "//S1 EXEC PGM=A\n//P PROC\n//D DD DSN=A,DISP=OLD\n//  PEND\n"
    assert _count(jcl) == {}
    assert ORACLE.index("plain text\n") == {}
