"""#3752: a porting ticket for every program with business logic, by default.

A real scan of a small estate -- a batch program (a JCL step runs it with a PARM) and a
copybook -- through the refractor and cobol-to-java pins what a ticket carries: the service
to fill and its TODO methods, the overlay path, the chosen target stack (no local paths or
credentials), the program's line-numbered source and copybooks, its paragraphs, the verified
facts, the generated classes it imports, its worklist items, the porting rules and the
deliverable; the worklist links the program to its ticket; and the tickets are byte-identical
across two runs.
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import _public_methods

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
       01  TRANS-REC.
           COPY TRANREC.
       WORKING-STORAGE SECTION.
       01  WS-TOTAL          PIC S9(9)V99 VALUE 0.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT TRANS-FILE
           PERFORM 100-READ
           CLOSE TRANS-FILE
           GOBACK.
       100-READ.
           READ TRANS-FILE
           ADD TR-AMT TO WS-TOTAL.
"""
TRANREC = """\
           05  TR-ID            PIC X(8).
           05  TR-AMT           PIC S9(7)V99.
"""
JOB = """\
//NIGHTLY  JOB (ACCT),'POST'
//RUN      EXEC PGM=POSTIT,PARM='20260926'
//TRANS    DD DSN=APP.TRANS,DISP=SHR
"""


def _pipeline(repo, out):
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


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    base = tmp_path_factory.mktemp("port_tickets")
    repo = base / "src_estate"
    for rel, text in {"cbl/POSTIT.cbl": POSTIT, "cpy/TRANREC.cpy": TRANREC, "jcl/NIGHTLY.jcl": JOB}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    runs = []
    for n in (1, 2):
        out = base / f"run{n}"
        out.mkdir()
        runs.append(_pipeline(repo, out))
    return runs


def test_every_program_with_business_logic_gets_a_ticket(generated):
    java = generated[0]
    t = json.loads((java / "ai_agent_jobs/POSTIT_port_ticket.json").read_text())
    assert t["ticket"] == "PORT-POSTIT" and t["status"] == "open"
    assert t["target"]["file"] == "src/main/java/com/gitgalaxy/modernized/service/PostitService.java"
    assert t["target"]["overlay"] == "port/service/PostitService.java"
    assert "public int runBatch(List<Dd> dds, String parm)" in t["target"]["methods_to_port"]
    assert t["target"]["config"]["java"]["version"] == 17 and t["target"]["config"]["database"] == "postgresql"
    assert "header_file" not in json.dumps(t["target"]["config"]) and "username" not in json.dumps(t)


def test_a_ticket_carries_the_source_the_facts_and_the_generated_api(generated):
    t = json.loads((generated[0] / "ai_agent_jobs/POSTIT_port_ticket.json").read_text())
    jobs = generated[0] / "ai_agent_jobs"
    assert t["source"]["program"] == {"file": "cbl/POSTIT.cbl", "listing": "sources/cbl/POSTIT.cbl.lst"}
    text = (jobs / t["source"]["program"]["listing"]).read_text().splitlines()
    assert text[13] == "   14 |        PROCEDURE DIVISION." and len(text) == len(POSTIT.splitlines())
    assert t["source"]["copybooks"] == [{"file": "cpy/TRANREC.cpy", "listing": "sources/cpy/TRANREC.cpy.lst"}]
    assert "TR-AMT" in (jobs / "sources/cpy/TRANREC.cpy.lst").read_text()
    assert [p["name"] for p in t["paragraphs"]] == ["000-MAIN", "100-READ"]
    assert "com.gitgalaxy.modernized.batch.Dd" in [g["class"] for g in t["generated"]["imports"]]
    assert t["facts"]["program"]["file"] == "cbl/POSTIT.cbl" and t["worklist"]
    assert any("ROUNDED" in r for r in t["rules"]) and "equivalence" in t["deliverable"]["proof"]
    md = (generated[0] / "ai_agent_jobs/POSTIT_port_ticket.md").read_text()
    assert md.startswith("# PORT-POSTIT: port POSTIT (cobol, `cbl/POSTIT.cbl`")
    assert "- `cbl/POSTIT.cbl`: [sources/cbl/POSTIT.cbl.lst](sources/cbl/POSTIT.cbl.lst)" in md


def test_the_worklist_links_the_ticket_and_tickets_are_deterministic(generated):
    wl = json.loads((generated[0] / "migration_worklist.json").read_text())
    linked = [i for i in wl["items"] if i["program"] == "cbl/POSTIT.cbl"]
    assert linked and all(i.get("ticket") == "ai_agent_jobs/POSTIT_port_ticket.md" for i in linked)
    assert (
        "porting ticket [`ai_agent_jobs/POSTIT_port_ticket.md`]" in (generated[0] / "migration_worklist.md").read_text()
    )
    a, b = (g / "ai_agent_jobs/POSTIT_port_ticket.json" for g in generated)
    strip = lambda s: s.replace(generated[0].parent.name, "RUN").replace(generated[1].parent.name, "RUN")  # noqa: E731
    assert strip(a.read_text()).split('"full_skeleton"')[0] == strip(b.read_text()).split('"full_skeleton"')[0]


def test_public_methods_marks_the_todo_bodies():
    java = """public class S {
    public void kept(int a) {
        log.info("x");
    }

    /** TODO: port the PROCEDURE DIVISION main line; return its RETURN-CODE. */
    public int runBatch(List<Dd> dds, String parm) {
        return 0;
    }

    public void other() {
        // TODO: [AI AGENT] Implement extracted business rules here.
    }
}"""
    assert [(m["signature"], m["todo"]) for m in _public_methods(java)] == [
        ("public void kept(int a)", False), ("public int runBatch(List<Dd> dds, String parm)", True),
        ("public void other()", True)]  # fmt: skip
