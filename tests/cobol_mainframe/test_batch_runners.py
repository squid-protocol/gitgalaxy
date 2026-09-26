"""#3710: the program a batch runner runs.

IKJEFT01 / IKJEFT1B run what their SYSTSIN says (`RUN PROGRAM(x)`, `CALL`, a REXX
`EXEC`), in-stream or from a dataset member; DFSRRC00 runs the second positional of
PARM=. A real scan of a small estate with each form pins the reader (core/jcl_runners),
the engine (the STEP row's runs, an `EXEC PGM` call edge per load module resolved to the
program, job_steps' `runner_programs`, a member read from the source tree) and the Spring
Batch classification: a runner running an estate program is an application job whose
step calls that program's runBatch; one running only an IBM utility is a utility job;
one whose target is unknown stays a runner, saying what is missing.
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.core.jcl_runners import runner_targets
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

POSTIT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. POSTIT.
       PROCEDURE DIVISION.
           GOBACK.
"""

JOBS = {
    "jcl/DB2RUN.jcl": """\
//DB2RUN   JOB (ACCT),'DB2'
//RUN      EXEC PGM=IKJEFT01,DYNAMNBR=20
//SYSTSPRT DD SYSOUT=*
//SYSTSIN  DD *
  DSN SYSTEM(DB2P)
  RUN PROGRAM(POSTIT) PLAN(POSTPLN) -
      LIB('APP.LOADLIB')
  END
/*
""",
    "jcl/SQLRUN.jcl": """\
//SQLRUN   JOB (ACCT),'SQL'
//DDL      EXEC PGM=IKJEFT01
//SYSTSIN  DD *
  DSN SYSTEM(DB2P)
  RUN PROGRAM(DSNTEP2) PLAN(DSNTEP12)
  END
//SYSIN    DD *
  CREATE TABLE T (C CHAR(1));
/*
""",
    "jcl/IMSRUN.jcl": """\
//IMSRUN   JOB (ACCT),'IMS'
//BMP      EXEC PGM=DFSRRC00,
//             PARM='BMP,POSTIT,POSTPSB'
""",
    "jcl/MEMRUN.jcl": """\
//MEMRUN   JOB (ACCT),'MEMBER'
//RUN      EXEC PGM=IKJEFT01
//SYSTSIN  DD DISP=SHR,DSN=APP.CNTL(RUNPOST)
""",
    "jcl/GONERUN.jcl": """\
//GONERUN  JOB (ACCT),'GONE'
//RUN      EXEC PGM=IKJEFT01
//SYSTSIN  DD DISP=SHR,DSN=APP.CNTL(NOWHERE)
""",
    "jcl/BINDRUN.jcl": """\
//BINDRUN  JOB (ACCT),'BIND'
//BIND     EXEC PGM=IKJEFT01
//SYSTSIN  DD *
  DSN SYSTEM(DB2P)
  BIND PLAN(POSTPLN) MEMBER(POSTIT)
  END
/*
""",
    "jcl/REXXRUN.jcl": """\
//REXXRUN  JOB (ACCT),'REXX'
//TSO      EXEC PGM=IKJEFT1B
//SYSTSIN  DD *
 EXEC 'APP.EXEC(MYREXX)'
/*
""",
}


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("batch_runners")
    repo = base / "estate"
    files = {"cbl/POSTIT.cbl": POSTIT, "ctl/RUNPOST.ctl": "  DSN SYSTEM(DB2P)\n  RUN PROGRAM(POSTIT) -\n  PLAN(P2)\n",
             **JOBS}  # fmt: skip
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_the_reader_finds_each_form():
    got = [(r["runner"], r["via"], r["program"], r["plan"], r["at"]) for r in runner_targets(JOBS["jcl/DB2RUN.jcl"])]
    assert got == [("IKJEFT01", "RUN PROGRAM", "POSTIT", "POSTPLN", 6)]  # the `-` continuation is one command
    ims = runner_targets(JOBS["jcl/IMSRUN.jcl"])[0]
    assert (ims["program"], ims["region"], ims["psb"], ims["via"]) == ("POSTIT", "BMP", "POSTPSB", "DFSRRC00")
    mem = runner_targets(JOBS["jcl/MEMRUN.jcl"])[0]
    assert (mem["program"], mem["member"], mem["via"]) == (None, "RUNPOST", "SYSTSIN member")
    assert runner_targets(JOBS["jcl/REXXRUN.jcl"])[0]["via"] == "TSO EXEC"


def test_the_engine_records_the_step_and_a_call_edge(scanned):
    repo, db = scanned
    ir = load_galaxy_ir(db)
    ir.source_root = repo
    edges = {(f.file_path, c.target, c.resolves_to) for f in ir.files.values() for c in f.calls if c.form == "runner"}
    assert ("jcl/DB2RUN.jcl", "POSTIT", "cbl/POSTIT.cbl") in edges
    assert ("jcl/IMSRUN.jcl", "POSTIT", "cbl/POSTIT.cbl") in edges
    assert ("jcl/SQLRUN.jcl", "DSNTEP2", None) in edges  # an IBM utility: a call site, not a program here
    assert not any(t == "MYREXX" for _, t, _ in edges)  # a REXX exec is not a load module
    steps = {j["job"]: j["steps"][0]["runner_programs"] for j in ir.job_steps()}
    assert steps["DB2RUN"] == [{"program": "POSTIT", "via": "RUN PROGRAM", "source": "systsin",
                                "resolves_to": "cbl/POSTIT.cbl"}]  # fmt: skip
    assert steps["MEMRUN"] == [{"program": "POSTIT", "via": "RUN PROGRAM", "source": "member", "member": "RUNPOST",
                                "resolves_to": "cbl/POSTIT.cbl"}]  # fmt: skip
    assert steps["GONERUN"] == [{"program": None, "via": None, "source": "member", "member": "NOWHERE",
                                 "resolves_to": None}]  # fmt: skip
    ir.source_root = None  # without the source tree a member cannot be read: a finding, not a guess
    ir.__dict__.pop("_member_index", None)
    assert next(j for j in ir.job_steps() if j["job"] == "MEMRUN")["steps"][0]["runner_programs"][0]["program"] is None


def test_runner_jobs_become_application_utility_or_stay_runners(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    src = java / "src/main/java/com/gitgalaxy/modernized"
    listing = {j["job"]: j for j in json.loads((java / "src/main/resources/batch/jcl-jobs.json").read_text())}
    assert {n: j["kind"] for n, j in listing.items()} == {
        "DB2RUN": "application", "IMSRUN": "application", "MEMRUN": "application", "SQLRUN": "utility",
        "GONERUN": "runner", "REXXRUN": "runner", "BINDRUN": "utility"}  # fmt: skip
    assert "SYSTSIN member NOWHERE is not in the repository" in listing["GONERUN"]["reason"]
    assert "the REXX / CLIST exec MYREXX" in listing["REXXRUN"]["reason"]
    assert listing["BINDRUN"]["reason"] == "data utilities only (IKJEFT01 (TSO commands))"  # BIND: no program
    cfg = (src / "batch/Db2runJobConfig.java").read_text(encoding="utf-8")
    assert 'steps.program("RUN", "RUN", null, null, null, () -> postitService.runBatch(DDS_RUN, null))' in cfg
    svc = (src / "service/PostitService.java").read_text(encoding="utf-8")
    assert "job DB2RUN step RUN (jcl/DB2RUN.jcl:2) through IKJEFT01 (RUN PROGRAM)" in svc
    assert "through DFSRRC00 (DFSRRC00)" in svc
