"""
#4268: the record length / format a DD states (`DCB=(LRECL=..,RECFM=..)`, `DCB=LRECL=..`, bare `LRECL=` /
`RECFM=`) is `lrecl` / `recfm` on its job-flow DD row, carried through the master DB and the delta restore to
`GalaxyIR.job_dds` and the skeleton_export estate join. Presence-keyed: a DD that states nothing keeps its shape.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.job_flow import jcl_job_flow
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.tools.cobol_to_cobol import skeleton_export
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from scan_server import scan_to_db  # noqa: E402 -- the engine imported once a process


def _dd(operands):
    rows = jcl_job_flow(f"//J JOB\n//S EXEC PGM=X\n//D DD DSN=A.B,{operands}\n")
    ((row),) = [r for r in rows if r["kind"] == "DD"]
    return {k: row[k] for k in ("lrecl", "recfm") if k in row}


@pytest.mark.parametrize(
    "operands, want",
    [
        ("DISP=SHR,DCB=(LRECL=80,RECFM=FB)", {"lrecl": 80, "recfm": "FB"}),
        ("DISP=SHR,DCB=(RECFM=FB,LRECL=80,BLKSIZE=80)", {"lrecl": 80, "recfm": "FB"}),
        ("DISP=SHR,DCB=(RECFM=VB,LRECL=137,DSORG=PS)", {"lrecl": 137, "recfm": "VB"}),
        ("DISP=SHR,DCB=LRECL=60", {"lrecl": 60}),
        ("DISP=SHR,DCB=(LRECL=80)", {"lrecl": 80}),
        ("DISP=SHR,DCB=(RECFM=U,BLKSIZE=32760)", {"recfm": "U"}),
        ("DISP=SHR,DCB=(RECFM=FBA,LRECL=133)", {"lrecl": 133, "recfm": "FBA"}),
        ("DISP=SHR,DCB=(recfm=f,lrecl=10)", {"lrecl": 10, "recfm": "F"}),
        ("DISP=SHR,LRECL=80,RECFM=FB", {"lrecl": 80, "recfm": "FB"}),
        ("DISP=SHR,LRECL=80", {"lrecl": 80}),
        ("DISP=SHR,RECFM=FB", {"recfm": "FB"}),
        ("DISP=SHR,DCB=(LRECL=80,RECFM=FB),LRECL=100", {"lrecl": 100, "recfm": "FB"}),
        # states nothing: no key, no guess
        ("DISP=SHR", {}),
        ("DISP=SHR,DCB=(BLKSIZE=133)", {}),
        ("DISP=SHR,DCB=(*.SORTIN)", {}),
        ("DISP=SHR,DCB=*.S1.SORTIN", {}),
        ("DISP=SHR,DCB=MY.MODEL.DSCB", {}),
        ("DISP=SHR,DCB=(LRECL=0,RECFM=FB)", {"recfm": "FB"}),
        ("DISP=SHR,DCB=(LRECL=&LR,RECFM=FB)", {"recfm": "FB"}),
    ],
)
def test_every_stated_form_and_every_unstated_one(operands, want):
    assert _dd(operands) == want


def test_a_continued_dd_and_a_proc_dd_state_theirs_and_a_dsnless_dd_stays_out():
    text = (
        "//J JOB\n//P PROC\n//S1 EXEC PGM=X\n//IN DD DSN=A.B,DISP=SHR,\n//   DCB=(LRECL=80,RECFM=FB)\n//OUT DD SYSOUT=*,DCB=(LRECL=133)\n"
        "//   PEND\n//R EXEC PROC=P\n"
    )
    dds = [r for r in jcl_job_flow(text) if r["kind"] == "DD"]
    assert [(r["dd_name"], r.get("lrecl"), r.get("recfm"), r["in_proc"]) for r in dds] == [("IN", 80, "FB", "P")]


JCL = (
    "//NIGHTLY JOB 1\n"
    "//S1 EXEC PGM=SORT\n"
    "//SORTIN DD DSN=A.IN,DISP=SHR,DCB=(LRECL=80,RECFM=FB)\n"
    "//SORTOUT DD DSN=A.OUT,DISP=(NEW,CATLG),LRECL=80,RECFM=FB\n"
    "//OTHER DD DSN=A.PLAIN,DISP=SHR\n"
)


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("dcb")
    repo = base / "jobs"
    repo.mkdir()
    (repo / "NIGHTLY.jcl").write_text(JCL, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def _got(db):
    return {r["dd"]: {k: r[k] for k in ("lrecl", "recfm") if k in r} for r in load_galaxy_ir(db).job_dds()}


WANT = {"SORTIN": {"lrecl": 80, "recfm": "FB"}, "SORTOUT": {"lrecl": 80, "recfm": "FB"}, "OTHER": {}}


def test_a_real_scan_reaches_job_dds(scanned):
    assert _got(scanned) == WANT


def test_an_unchanged_file_keeps_its_attributes_through_a_delta_scan(scanned, tmp_path):
    session = {"target": "jobs", "git_audit": {"commit_hash": "x", "latest_commit_date": "2026-10-29T00:00:00Z"}}
    cache = StateRehydrator(str(scanned)).load_state("jobs")["ram_cache"]
    db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, session, str(db))
    assert _got(db) == WANT


def test_the_estate_join_carries_them():
    assert skeleton_export.ESTATE_JOINS["job_dds"] == "JCL job flow"
