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


def test_other_in_stream_dds_and_a_bare_deck_are_not_kept():
    assert _rows("//J JOB\n//S EXEC PGM=X\n//SYSTSIN DD *\n  RUN PROGRAM(P)\n/*\n") == []
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
