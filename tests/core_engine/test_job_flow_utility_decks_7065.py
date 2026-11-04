"""
#7065 (Batch Badlands, #4890): the in-stream control decks of the utilities the level has not planted yet (ADRDSSU and
IEBIMAGE read SYSIN; DSNUTILB reads SYSIN; BPXBATCH reads STDPARM / STDIN / STDENV; IKJEFT01 reads SYSTSIN) are INSTREAM
job-flow rows with their body as written. The class: every utility x control DD, with a PROCSTEP qualifier, a hyphen
or `+` continuation and a `/*` or `DLM=` terminator.
"""

import pytest

from gitgalaxy.core.job_flow import is_control_dd, jcl_job_flow

JCL = """\
//UTILJOB  JOB 'X',CLASS=A
//DUMP     EXEC PGM=ADRDSSU
//SYSPRINT DD SYSOUT=*
//TAPE     DD DSN=BACKUP.DUMP,DISP=(NEW,CATLG)
//SYSIN    DD *
  DUMP DATASET(INCLUDE(PROD.**)) -
       OUTDDNAME(TAPE) COMPRESS
/*
//IMG      EXEC PGM=IEBIMAGE
//SYSIN    DD *
  FCB1 CHARS=(GS10)
/*
//DB       EXEC PGM=DSNUTILB,PARM='DB2P,UTIL1'
//SYSIN    DD *
  RUNSTATS TABLESPACE DB1.TS1
/*
//UNIX     EXEC PGM=BPXBATCH
//STDPARM  DD *
SH ls -l
/*
//STDENV   DD *
HOME=/u/batch
/*
//TSO      EXEC PGM=IKJEFT01
//SYSTSIN  DD DATA,DLM=ZZ
  DSN SYSTEM(DB2P)
  BIND PLAN(P1) MEMBER(M1) +
       ACTION(REPLACE)
  END
/*
ZZ
//PRC      EXEC PROC=UTILP
//DMP.SYSIN DD *
  RESTORE INDDNAME(TAPE)
"""


def _rows():
    return [r for r in jcl_job_flow(JCL) if r["kind"] == "INSTREAM"]


def test_each_utility_deck_is_one_row_with_its_body_as_written():
    got = [(r["step_name"], r["dd_name"], r["line"], r["instream"]) for r in _rows()]
    assert got == [
        ("DUMP", "SYSIN", 5, "  DUMP DATASET(INCLUDE(PROD.**)) -\n       OUTDDNAME(TAPE) COMPRESS"),
        ("IMG", "SYSIN", 10, "  FCB1 CHARS=(GS10)"),
        ("DB", "SYSIN", 14, "  RUNSTATS TABLESPACE DB1.TS1"),
        ("UNIX", "STDPARM", 18, "SH ls -l"),
        ("UNIX", "STDENV", 21, "HOME=/u/batch"),
        (
            "TSO",
            "SYSTSIN",
            25,
            "  DSN SYSTEM(DB2P)\n  BIND PLAN(P1) MEMBER(M1) +\n       ACTION(REPLACE)\n  END\n/*",
        ),
        ("DMP", "SYSIN", 33, "  RESTORE INDDNAME(TAPE)"),
    ]


@pytest.mark.parametrize("name", ["SYSIN", "SYSTSIN", "STDPARM", "STDIN", "STDENV", "DMP.SYSIN", "TOOLIN", "SORTCNTL"])
def test_control_dd_names(name):
    assert is_control_dd(name)


@pytest.mark.parametrize("name", ["SYSPRINT", "TAPE", "SYSUT1", "SORTIN", None, ""])
def test_data_dd_names_are_not_control_decks(name):
    assert not is_control_dd(name)
