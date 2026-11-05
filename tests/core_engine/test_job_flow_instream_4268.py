"""
#4268: a JCL step's in-stream control deck (SYSIN / SYMNAMES / SORTCNTL / DFSPARM) is an INSTREAM job-flow row,
carried through the master DB and the delta restore to `GalaxyIR.job_sysin`. The class is every `DD *` / `DD DATA`
form: terminated by `/*`, by the next `//` statement, or by a `DLM=`; a PROCSTEP override; and a deck in a PROC.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.job_flow import jcl_job_flow
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from scan_server import scan_to_db  # noqa: E402 -- the engine imported once a process

JCL = """\
//SORTJOB  JOB 'X',CLASS=A
//S1       EXEC PGM=SORT
//SORTIN   DD DSN=A.B,DISP=SHR
//SYMNAMES DD *
KEY,1,5,CH
/*
//SYSIN    DD *
  SORT FIELDS=(KEY,A)
  INCLUDE COND=(1,3,CH,EQ,C'A//B')
  OPTION COPY
/*
//S2       EXEC PGM=ICEMAN
//SYSIN    DD DATA,DLM=ZZ
  SORT FIELDS=COPY
/*
ZZ
//S3       EXEC PROC=SORTP
//SORT1.SORTCNTL DD *
  OPTION EQUALS
//S4       EXEC PGM=IEFBR14
//SYSIN    DD DSN=A.CARDS,DISP=SHR
"""


def _rows(text=JCL):
    return [r for r in jcl_job_flow(text) if r["kind"] == "INSTREAM"]


def test_every_in_stream_form_is_one_row_with_its_body_as_written():
    got = [(r["step_name"], r["dd_name"], r["line"], r["instream"]) for r in _rows()]
    assert got == [
        ("S1", "SYMNAMES", 4, "KEY,1,5,CH"),
        ("S1", "SYSIN", 7, "  SORT FIELDS=(KEY,A)\n  INCLUDE COND=(1,3,CH,EQ,C'A//B')\n  OPTION COPY"),
        ("S2", "SYSIN", 13, "  SORT FIELDS=COPY\n/*"),
        ("SORT1", "SORTCNTL", 18, "  OPTION EQUALS"),
    ]


def test_a_dsn_sysin_and_the_existing_rows_are_unchanged():
    rows = jcl_job_flow(JCL)
    assert [r["dsn"] for r in rows if r["kind"] == "DD"] == ["A.B", "A.CARDS"]
    assert [r["step_name"] for r in rows if r["kind"] == "STEP"] == ["S1", "S2", "S3", "S4"]
    assert all("instream" not in r for r in rows if r["kind"] != "INSTREAM")


UTILITY_JCL = """\
//UTILJOB  JOB 1
//SH       EXEC PGM=BPXBATCH
//STDPARM  DD *
SH /u/app/run.sh -v
/*
//STDIN    DD *
input line
/*
//STDENV   DD DATA
HOME=/u/app
/*
//BIND     EXEC PGM=IKJEFT01
//SYSTSIN  DD *
 DSN SYSTEM(DB2P)
 BIND PACKAGE(COLL) -
   MEMBER(PGM1)
 END
/*
//RESTORE  EXEC PROC=DSSP
//DUMP.SYSIN DD *
 DUMP DATASET(INCLUDE(PROD.**)) -
   OUTDDNAME(TAPE)
//UTIL     EXEC PGM=DSNUTILB,PARM='DB2P,UT1'
//SYSIN    DD *
-- runstats
 RUNSTATS TABLESPACE DB1.TS1
//COPY     EXEC PGM=IEBGENER
//SYSUT1   DD *
DATA LINE
//SORTIN   DD *
MORE DATA
"""


def test_bpxbatch_ikjeft01_adrdssu_and_dsnutilb_decks_are_rows_and_data_decks_are_not():
    got = [(r["step_name"], r["dd_name"], r["instream"]) for r in _rows(UTILITY_JCL)]
    assert got == [
        ("SH", "STDPARM", "SH /u/app/run.sh -v"),
        ("SH", "STDIN", "input line"),
        ("SH", "STDENV", "HOME=/u/app"),
        ("BIND", "SYSTSIN", " DSN SYSTEM(DB2P)\n BIND PACKAGE(COLL) -\n   MEMBER(PGM1)\n END"),
        ("DUMP", "SYSIN", " DUMP DATASET(INCLUDE(PROD.**)) -\n   OUTDDNAME(TAPE)"),
        ("UTIL", "SYSIN", "-- runstats\n RUNSTATS TABLESPACE DB1.TS1"),
    ]


def test_a_systsin_deck_keeps_its_runs_channel():
    rows = jcl_job_flow("//J JOB\n//S EXEC PGM=IKJEFT01\n//SYSTSIN DD *\n  RUN PROGRAM(P)\n/*\n")
    assert [r["instream"] for r in rows if r["kind"] == "INSTREAM"] == ["  RUN PROGRAM(P)"]


def test_other_in_stream_dds_and_a_bare_deck_are_not_kept():
    assert _rows("//J JOB\n//S EXEC PGM=X\n//SYSUT1 DD *\n  DATA\n/*\n//SORTIN DD *\n  D\n/*\n") == []
    ((row),) = _rows("//J JOB\n//S EXEC PGM=X\n//SYSIN DD *\n")
    assert row["instream"] == ""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("instream")
    repo = base / "jobs"
    repo.mkdir()
    (repo / "SORTJOB.jcl").write_text(JCL, encoding="utf-8")
    (repo / "PROCJOB.jcl").write_text(
        "//PROCJOB  JOB 1\n//SORTP    PROC\n//P1       EXEC PGM=SORT\n//SYSIN    DD *\n  SORT FIELDS=COPY\n/*\n"
        "//         PEND\n//R1       EXEC PROC=SORTP\n",
        encoding="utf-8",
    )
    return scan_to_db(repo, base / "scan")


def test_a_real_scan_reaches_job_sysin(scanned):
    got = [(r["job"], r["step"], r["program"], r["proc_step"], r["dd"], r["line"], r["lines"])
           for r in load_galaxy_ir(scanned).job_sysin()]  # fmt: skip
    assert got == [
        ("SORTJOB", "S1", "SORT", None, "SYMNAMES", 4, 1),
        ("SORTJOB", "S1", "SORT", None, "SYSIN", 7, 3),
        ("SORTJOB", "S2", "ICEMAN", None, "SYSIN", 13, 2),
        ("SORTJOB", "S3", None, "SORT1", "SORTCNTL", 18, 1),
    ]  # PROCJOB's deck belongs to the procedure, not to a job step
    body = next(r["body"] for r in load_galaxy_ir(scanned).job_sysin() if r["dd"] == "SYSIN" and r["line"] == 7)
    assert body == "  SORT FIELDS=(KEY,A)\n  INCLUDE COND=(1,3,CH,EQ,C'A//B')\n  OPTION COPY"


def test_an_unchanged_file_keeps_its_decks_through_a_delta_scan(scanned, tmp_path):
    session = {"target": "jobs", "git_audit": {"commit_hash": "x", "latest_commit_date": "2026-10-29T00:00:00Z"}}
    cache = StateRehydrator(str(scanned)).load_state("jobs")["ram_cache"]
    flow = cache["SORTJOB.jcl"]["job_flow"]
    assert [r["instream"] for r in flow if r["kind"] == "INSTREAM"][0] == "KEY,1,5,CH"
    db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, session, str(db))
    assert [r["body"] for r in load_galaxy_ir(db).job_sysin()] == [
        r["body"] for r in load_galaxy_ir(scanned).job_sysin()
    ]


ICETOOL_JCL = """\
//TOOLJOB  JOB 'X',CLASS=A
//S1       EXEC PGM=ICETOOL
//TOOLMSG  DD SYSOUT=*
//IN1      DD DSN=A.B,DISP=SHR
//TOOLIN   DD *
  COPY FROM(IN1) TO(OUT1) USING(CTL1)
/*
//CTL1CNTL DD *
  OMIT COND=(1,2,CH,EQ,C'XX')
/*
//SORTIN   DD *
data row that is not a control card
/*
//SYSUT1   DD *
more data
/*
//CNTLLIB  DD *
too long a prefix for USING
/*
//S2       EXEC PROC=PRC
//S2.TOOLIN DD *
  COUNT FROM(IN1)
/*
"""


def _instream_dds(jcl):
    return [(r["step_name"], r["dd_name"]) for r in jcl_job_flow(jcl) if r["kind"] == "INSTREAM"]


def test_icetool_toolin_and_using_cntl_decks_are_instream_rows():
    got = _instream_dds(ICETOOL_JCL)
    assert ("S1", "TOOLIN") in got and ("S1", "CTL1CNTL") in got
    assert any(dd == "TOOLIN" and st == "S2" for st, dd in got)  # PROCSTEP override form


@pytest.mark.parametrize("dd", ["SORTIN", "SYSUT1", "CNTLLIB", "SYSTSIN"])
def test_data_and_non_using_in_stream_dds_are_still_not_kept(dd):
    assert dd not in {d for _, d in _instream_dds(ICETOOL_JCL)}


def test_is_control_dd_covers_the_class():
    from gitgalaxy.core.job_flow import is_control_dd

    for ok in ("SYSIN", "toolin", "S2.TOOLIN", "A1CNTL", "Z9$#CNTL", "SORTCNTL", "ctl1cntl"):
        assert is_control_dd(ok), ok
    for bad in ("CNTL", "ABCDECNTL", "SYSUT1", "CNTLLIB", "", None):
        assert not is_control_dd(bad), bad


# A DD statement whose operands run on to a `//` line keeps its deck; the row's `line` is the statement's LAST line,
# so the body starts on `line + 1` for every form (#7065).
CONTINUED_JCL = """\
//J       JOB 'X'
//S1      EXEC PGM=ICEMAN
//SYSIN   DD *,
//  DLM=ZZ
  SORT FIELDS=COPY
//NOT-A-STATEMENT
ZZ
//S2      EXEC PGM=IKJEFT01
//SYSTSIN DD DATA,
//* a comment between the lines
//  DLM=@@,
//  DCB=LRECL=80
  DSN SYSTEM(DB2A)
/*
@@
//S3      EXEC PGM=ICETOOL
//TOOLIN  DD *,DCB=(LRECL=80,
//   RECFM=FB)
  COPY FROM(IN) TO(OUT)
//SORTIN  DD *,
//  DLM=ZZ
data
ZZ
//S4      EXEC PGM=X
"""


def test_a_dd_whose_operands_continue_keeps_its_deck_and_delimiter():
    got = [(r["step_name"], r["dd_name"], r["line"], r["instream"]) for r in _rows(CONTINUED_JCL)]
    assert got == [
        ("S1", "SYSIN", 4, "  SORT FIELDS=COPY\n//NOT-A-STATEMENT"),
        ("S2", "SYSTSIN", 12, "  DSN SYSTEM(DB2A)\n/*"),
        ("S3", "TOOLIN", 18, "  COPY FROM(IN) TO(OUT)"),
    ]
    lines = CONTINUED_JCL.split("\n")
    for step, dd, line, body in got:
        assert lines[line].rstrip() == body.split("\n")[0]  # the body starts on the line after the row's `line`


def test_a_continued_data_dd_is_still_not_kept():
    assert "SORTIN" not in {d for _, d in _instream_dds(CONTINUED_JCL)}


def test_a_single_line_dd_keeps_its_own_line():
    assert [r["line"] for r in _rows()] == [4, 7, 13, 18]
