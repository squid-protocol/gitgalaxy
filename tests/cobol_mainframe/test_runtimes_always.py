"""#4039: every project with a program to port gets the CobolRecords and CobolEdit runtimes.

Every port ticket's rules send the porter through them -- CobolRecords.numval (#3831), zoned / packed /
binary, sortKey (#3822), width / fit (#3985), CobolEdit.format (#3827) -- but they were generated only
beside a VSAM entity, or (#3989) for a program with CICS evidence. A batch-only estate over sequential
datasets, or a CICS program whose only command is SEND TEXT, got rules naming classes it did not have: the
port did not compile, or hand-wrote the parser the rules forbid. A real scan of such an estate through the
refractor and cobol-to-java backs this.
"""

import json
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

# Batch over a sequential dataset: no VSAM store, no CICS.
PAYRPT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYRPT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT PAY-FILE ASSIGN TO PAYIN.
       DATA DIVISION.
       FILE SECTION.
       FD  PAY-FILE.
       01  PAY-REC.
           05 PAY-ID          PIC X(8).
           05 PAY-AMT         PIC S9(7)V99.
       WORKING-STORAGE SECTION.
       01  WS-OUT            PIC ZZZ,ZZ9.99-.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT PAY-FILE
           READ PAY-FILE
           MOVE PAY-AMT TO WS-OUT
           DISPLAY WS-OUT
           CLOSE PAY-FILE
           GOBACK.
"""
# CICS, but only SEND TEXT: no transaction, resource, COMMAREA or LINK the forge counts as CICS evidence.
SHOWAMT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SHOWAMT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-AMT        PIC S9(7)V99 VALUE 1234.5.
       01  WS-OUT        PIC ZZZ,ZZ9.99-.
       01  WS-MSG        PIC X(40).
       PROCEDURE DIVISION.
       000-MAIN.
           MOVE WS-AMT TO WS-OUT
           STRING 'AMOUNT ' WS-OUT DELIMITED BY SIZE INTO WS-MSG
           EXEC CICS SEND TEXT FROM(WS-MSG) LENGTH(40) END-EXEC
           EXEC CICS RETURN END-EXEC.
"""
JOB = """\
//PAYJOB   JOB CLASS=A
//STEP1    EXEC PGM=PAYRPT
//PAYIN    DD DSN=APP.PAY.DAILY,DISP=SHR
"""


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    base = tmp_path_factory.mktemp("runtimes_always")
    repo = base / "src_estate"
    for rel, text in {"cbl/PAYRPT.cbl": PAYRPT, "cbl/SHOWAMT.cbl": SHOWAMT, "jcl/PAYJOB.jcl": JOB}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    out = base / "run"
    out.mkdir()
    work = out / "estate"
    shutil.copytree(repo, work)
    db = scan_to_db(repo, out / "scan")
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = out.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(out / "none.txt")]):
        java_controller.main()
    (java,) = out.glob("estate_gitgalaxy_java_spring_*")
    return java


def test_a_project_without_vsam_or_cics_evidence_gets_the_runtimes(generated):
    vsam = generated / "src/main/java/com/gitgalaxy/modernized/entity/vsam"
    assert sorted(p.name for p in vsam.glob("*.java")) == ["CobolEdit.java", "CobolRecords.java"]  # no entity
    assert "public final class CobolRecords" in (vsam / "CobolRecords.java").read_text(encoding="utf-8")
    assert "public static String format(" in (vsam / "CobolEdit.java").read_text(encoding="utf-8")
    assert not list(generated.rglob("repository/vsam/*.java"))  # still no VSAM store


def test_every_ticket_names_runtimes_the_project_has(generated):
    jobs = generated / "ai_agent_jobs"
    for key in ("PAYRPT", "SHOWAMT"):
        rules = " ".join(json.loads((jobs / f"{key}_port_ticket.json").read_text(encoding="utf-8"))["rules"])
        assert "CobolRecords.numval" in rules and "CobolEdit.format" in rules


@pytest.mark.skipif(shutil.which("javac") is None, reason="no JDK")
def test_the_runtimes_compile_on_their_own(generated, tmp_path):
    vsam = generated / "src/main/java/com/gitgalaxy/modernized/entity/vsam"
    assert len(list(vsam.glob("*.java"))) == 2
    subprocess.run(["javac", "-encoding", "UTF-8", "-d", str(tmp_path), *map(str, sorted(vsam.glob("*.java")))],
                   check=True)  # fmt: skip
