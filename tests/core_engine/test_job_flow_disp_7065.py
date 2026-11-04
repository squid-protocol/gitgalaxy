"""
#7065 (Batch Badlands, #4891): a DD's abnormal-end disposition (the third DISP subparameter, z/OS MVS JCL Reference,
DISP) is kept as `disp_abnormal`, and a DD that names no dataset but asks for SPACE / UNIT / VOL is a TEMP row (a
system-named temporary dataset). The class: every DISP shape and every DSN-less DD kind.
"""

import pytest

from gitgalaxy.core.job_flow import jcl_job_flow


def _dd(operands: str) -> dict:
    rows = jcl_job_flow(f"//J JOB\n//S1 EXEC PGM=X\n//DD1 DD {operands}\n")
    return next(r for r in rows if r.get("dd_name") == "DD1")


@pytest.mark.parametrize(
    ("disp", "disp_value", "normal", "abnormal"),
    [
        ("(NEW,CATLG,DELETE)", "NEW", "CATLG", "DELETE"),
        ("(MOD,PASS,KEEP)", "MOD", "PASS", "KEEP"),
        ("(OLD,DELETE,UNCATLG)", "OLD", "DELETE", "UNCATLG"),
        ("(NEW,,DELETE)", "NEW", None, "DELETE"),
        ("(,CATLG,CATLG)", "NEW", "CATLG", "CATLG"),
        ("(NEW,CATLG)", "NEW", "CATLG", None),
        ("(NEW,PASS)", "NEW", "PASS", None),
        ("(NEW)", "NEW", None, None),
        ("SHR", "SHR", None, None),
        ("OLD", "OLD", None, None),
        ("(NEW,CATLG,BOGUS)", "NEW", "CATLG", None),
    ],
)
def test_every_disp_shape(disp, disp_value, normal, abnormal):
    row = _dd(f"DSN=A.B,DISP={disp}")
    assert row["kind"] == "DD" and row["disp"] == disp_value
    assert row.get("disp_normal") == normal
    assert row.get("disp_abnormal") == abnormal
    assert ("disp_abnormal" in row) == (abnormal is not None)  # presence-keyed


def test_a_temporary_named_dsn_keeps_its_disp_and_stays_a_dd_row():
    row = _dd("DSN=&&TMP,DISP=(NEW,PASS,DELETE),UNIT=SYSDA,SPACE=(CYL,(1,1))")
    assert (row["kind"], row["dsn"], row["disp_normal"], row["disp_abnormal"]) == ("DD", "&&TMP", "PASS", "DELETE")


@pytest.mark.parametrize(
    "operands",
    [
        "UNIT=SYSDA,SPACE=(CYL,(5,5))",
        "SPACE=(TRK,1)",
        "UNIT=SYSDA",
        "VOL=SER=WORK01,UNIT=3390",
        "DISP=(NEW,DELETE),UNIT=SYSDA",
    ],
)
def test_a_dsnless_dd_with_space_unit_or_vol_is_a_temp_row(operands):
    row = _dd(operands)
    assert row["kind"] == "TEMP" and row["step_name"] == "S1" and row.get("dsn") is None


@pytest.mark.parametrize(
    ("operands", "kind"),
    [
        ("DUMMY", "DUMMY"),
        ("SYSOUT=*", "SYSOUT"),
        ("DSN=NULLFILE", "DUMMY"),
        ("DSN=A.B,DISP=SHR", "DD"),
        ("DSN=A.B,UNIT=SYSDA,DISP=SHR", "DD"),
    ],
)
def test_other_dd_kinds_are_not_temp(operands, kind):
    assert _dd(operands)["kind"] == kind


@pytest.mark.parametrize(
    "operands",
    ["*", "DATA", "DDNAME=OTHER", "SUBSYS=(JES2,X)", "PATH='/u/x'", "DCB=*.S0.DD0", "DYNAM", "DCB=(LRECL=80)"],
)
def test_in_stream_ddname_subsys_path_and_attribute_only_dds_are_not_temp(operands):
    jcl = f"//J JOB\n//S1 EXEC PGM=X\n//DD1 DD {operands}\ndata\n/*\n"
    assert not [r for r in jcl_job_flow(jcl) if r["kind"] in ("TEMP", "DD") and r["dd_name"] == "DD1"]


def test_a_temp_dd_in_a_proc_and_a_continued_one_and_old_shapes_unchanged():
    jcl = "//P PROC\n//S1 EXEC PGM=SORT\n//SORTWK01 DD UNIT=SYSDA,\n//  SPACE=(CYL,(5,5))\n//SORTOUT DD DSN=A.B,DISP=SHR\n// PEND\n"
    rows = jcl_job_flow(jcl)
    temp = [r for r in rows if r["kind"] == "TEMP"]
    assert [(r["dd_name"], r["in_proc"]) for r in temp] == [("SORTWK01", "P")]
    out = next(r for r in rows if r["kind"] == "DD")
    assert "disp_abnormal" not in out and "disp_normal" not in out
