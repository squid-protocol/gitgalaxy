"""#3622: JCL job flow -> Spring Batch jobs.

A real scan of a small estate: NIGHTLY (IEFBR14 -> SORT with in-stream cards -> a program
step with COND=(4,LT) reading a GDG generation -> a cataloged PROC running IEBGENER),
plus a build job (IGYCRCTL), a runner (IKJEFT01) and a utility-only job (IDCAMS).
Pinned: GalaxyIR.job_dds (DDs by step order, PROC DDs, GDG split), the classification
listing, the job config (steps, tasklets, COND, DDs), the program's batch entry, the
manifest, the worklist and the audit. The generated Java compiles in java_target_matrix;
the runtime was exercised in a generated CardDemo project.
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

NIGHTLY = """\
//NIGHTLY  JOB (ACCT),'NIGHTLY RUN',CLASS=A,MSGCLASS=X
//CLEAN    EXEC PGM=IEFBR14
//OLD      DD DSN=APP.WORK.OUT,DISP=(MOD,DELETE,DELETE)
//SORT1    EXEC PGM=SORT
//SORTIN   DD DSN=APP.TRANS.IN,DISP=SHR
//SORTOUT  DD DSN=APP.TRANS.SORTED(+1),DISP=(NEW,CATLG,DELETE)
//SYSIN    DD *
  SORT FIELDS=(1,10,CH,A)
/*
//RUN      EXEC PGM=POSTIT,COND=(4,LT)
//TRANS    DD DSN=APP.TRANS.SORTED(+1),DISP=SHR
//COPY     EXEC COPYP
"""

COPYP = """\
//COPYP    PROC
//GEN      EXEC PGM=IEBGENER
//SYSUT1   DD DSN=APP.TRANS.IN,DISP=SHR
//SYSUT2   DD DSN=APP.TRANS.BACKUP,DISP=(NEW,CATLG)
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//         PEND
"""

POSTIT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. POSTIT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT TRANS-FILE ASSIGN TO TRANS.
       DATA DIVISION.
       FILE SECTION.
       FD  TRANS-FILE.
       01  TRANS-REC          PIC X(80).
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT TRANS-FILE
           CLOSE TRANS-FILE
           GOBACK.
"""

OTHER_JOBS = {
    "jcl/COMPILE.jcl": "//COMPILE  JOB (ACCT),'BUILD'\n//COB      EXEC PGM=IGYCRCTL\n//SYSIN    DD DSN=APP.SRC(POSTIT),DISP=SHR\n",
    "jcl/DB2RUN.jcl": "//DB2RUN   JOB (ACCT),'DB2'\n//TSO      EXEC PGM=IKJEFT01\n//SYSTSPRT DD SYSOUT=*\n",
    "jcl/LOAD.jcl": "//LOAD     JOB (ACCT),'LOAD'\n//DEF      EXEC PGM=IDCAMS\n//SYSPRINT DD SYSOUT=*\n",
}


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("batch_jobs")
    repo = base / "estate"
    files = {"jcl/NIGHTLY.jcl": NIGHTLY, "proc/COPYP.prc": COPYP, "cbl/POSTIT.cbl": POSTIT, **OTHER_JOBS}
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_job_dds_follow_step_order_expand_the_proc_and_split_the_generation(scanned):
    rows = [r for r in load_galaxy_ir(scanned[1]).job_dds() if r["job"] == "NIGHTLY"]
    got = [(r["step"], r["proc_step"], r["dd"], r["dsn"], r["generation"]) for r in rows]
    assert ("CLEAN", None, "OLD", "APP.WORK.OUT", None) in got
    assert ("SORT1", None, "SORTOUT", "APP.TRANS.SORTED", "+1") in got  # the generation apart
    assert ("RUN", None, "TRANS", "APP.TRANS.SORTED", "+1") in got
    assert ("COPY", "GEN", "SYSUT2", "APP.TRANS.BACKUP", None) in got  # the PROC's own DDs
    assert next(r for r in rows if r["dd"] == "OLD")["disp_normal"] == "DELETE"  # (MOD,DELETE,DELETE)
    gen = next(r for r in rows if r["dd"] == "SYSUT1")
    assert gen["source"] == "proc/COPYP.prc" and gen["file"] == "jcl/NIGHTLY.jcl"


def test_the_jobs_become_spring_batch_jobs(scanned, tmp_path):
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
        "NIGHTLY": "application", "COMPILE": "build", "DB2RUN": "runner", "LOAD": "utility"}  # fmt: skip
    assert listing["NIGHTLY"]["generated"] == "NightlyJobConfig" and listing["LOAD"]["generated"] is None

    cfg = (src / "batch/NightlyJobConfig.java").read_text(encoding="utf-8")
    assert 'return new JobBuilder("NIGHTLY", jobRepository)' in cfg
    order = [cfg.index(f'new StepBuilder("{s}"') for s in ("CLEAN", "SORT1", "RUN", "COPY.GEN")]
    assert order == sorted(order)  # JCL order, the PROC's step expanded
    assert 'steps.iefbr14("CLEAN", "CLEAN", null, null, null, DDS_CLEAN)' in cfg
    assert 'steps.utility("SORT1", "SORT1", null, null, null, "SORT", "SORT1 runs the utility SORT' in cfg
    assert 'steps.program("RUN", "RUN", null, "(4,LT)", null, () -> postitService.runBatch(DDS_RUN))' in cfg
    assert 'steps.copy("COPY.GEN", "COPY.GEN", null, null, null, DDS_COPY_GEN)' in cfg
    assert 'new Dd("SORTOUT", "APP.TRANS.SORTED", "NEW", "CATLG", "+1")' in cfg  # DISP=(NEW,CATLG,DELETE)
    assert 'new Dd("OLD", "APP.WORK.OUT", "MOD", "DELETE", null)' in cfg  # IEFBR14's delete idiom
    assert 'new Dd("SYSUT1", "APP.TRANS.IN", "SHR", null, null)' in cfg
    for runtime in ("Dd", "DatasetResolver", "JclConditions", "JclSteps", "JclJobLauncher", "BatchJobController"):
        assert (src / f"batch/{runtime}.java").is_file()
    assert not (src / "batch/Db2runJobConfig.java").exists() and not (src / "batch/CompileJobConfig.java").exists()

    svc = (src / "service/PostitService.java").read_text(encoding="utf-8")
    assert "The batch entry (#3622): run by job NIGHTLY step RUN (jcl/NIGHTLY.jcl:10)." in svc
    assert "    public int runBatch(List<Dd> dds) {" in svc
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "  • Batch jobs (#3622)       : 4 JCL jobs -- 1 application (generated: 4 steps, 1 utility steps to " \
           "port), 1 runner, 1 utility, 1 build" in audit  # fmt: skip

    manifest = json.loads((java / "traceability.json").read_text(encoding="utf-8"))
    run = next(a for a in manifest["artifacts"] if a["symbol"] == "NightlyJobConfig#RUN")
    assert run["facts"][0]["source"] == "jcl/NIGHTLY.jcl:10" and run["facts"][0]["ledger_field"] == "JCL job flow"
    cats = {i["category"] for i in json.loads((java / "migration_worklist.json").read_text())["items"]}
    assert {"batch-utility", "business-logic"} <= cats  # SORT1; POSTIT's main line
