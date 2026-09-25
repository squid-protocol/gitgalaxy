import json
import sys
from unittest.mock import patch

import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import TraceLog


def test_tracelog_records_facts_and_todos():
    # facts cite their section's ledger field and field-testing status from one source
    trace = TraceLog(
        {"uow_handlers": "units of work and handlers"},
        {"units of work and handlers": {"status": "field-tested", "tested_on_public": 6, "tested_on_private": 1}},
    )
    facts = [
        {
            "source": "COACTUPC.cbl:42",
            "section": "uow_handlers",
            "ledger_field": "uow_handlers",
            "field_testing": "untested",
        }
    ]
    todos = ["TODO: map something"]

    trace.record(
        "com/gitgalaxy/modernized/service/CoactupcService.java",
        "CoactupcService#commitPointL42",
        "commit",
        facts,
        todos,
    )

    gen_from = {"gitgalaxy_commit": "test-hash"}
    d = trace.as_dict(gen_from)
    assert d["generated_from"] == gen_from
    assert len(d["artifacts"]) == 1

    entry = d["artifacts"][0]
    assert entry["file"] == "com/gitgalaxy/modernized/service/CoactupcService.java"
    assert entry["symbol"] == "CoactupcService#commitPointL42"
    assert entry["kind"] == "commit"
    assert entry["facts"] == [
        {
            "source": "COACTUPC.cbl:42",
            "section": "uow_handlers",
            "ledger_field": "units of work and handlers",
            "field_testing": "field-tested (6 public / 1 private estates)",
        }
    ]
    assert entry["todos"] == todos
    # the same symbol twice is kept once; a class-level entry is named after its class
    trace.record(
        "com/gitgalaxy/modernized/service/CoactupcService.java", "CoactupcService#commitPointL42", "commit", facts
    )
    trace.record("src/main/java/x/dto/contract/CarddemoCommarea.java", "Class", "commarea-dto", [])
    symbols = [e["symbol"] for e in trace.as_dict({})["artifacts"]]
    assert symbols.count("CoactupcService#commitPointL42") == 1 and "CarddemoCommarea" in symbols


ACCTCOM = """\
       01  ACCT-COMMAREA.
           05 CA-ACCT-ID      PIC 9(11).
           05 CA-NAME         PIC X(20).
"""

MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY ACCTCOM.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS LINK PROGRAM('ACCTINQ') COMMAREA(ACCT-COMMAREA) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

ACCTINQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.
       DATA DIVISION.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05 LK-ACCT-ID      PIC 9(11).
           05 LK-NAME         PIC X(20).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""

CSD = """\
 DEFINE TRANSACTION(MENU) GROUP(APP)
        PROGRAM(MENU)
"""


def test_the_manifest_traces_real_generated_code_to_its_cobol(tmp_path):
    """A real scan: every artifact's file exists, and an endpoint, a service call and a DTO
    field each name their COBOL source, ledger field and field-testing status."""
    import shutil

    import gitgalaxy.cobol_refractor_controller as refractor
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    repo = tmp_path / "estate"
    for rel, text in {"cbl/MENU.cbl": MENU, "cbl/ACCTINQ.cbl": ACCTINQ, "cpy/ACCTCOM.cpy": ACCTCOM,
                      "csd/APP.csd": CSD}.items():  # fmt: skip
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    db = scan_to_db(repo, tmp_path / "scan")
    work = tmp_path / "work" / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = (tmp_path / "work").glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = (tmp_path / "work").glob("estate_gitgalaxy_java_spring_*")
    manifest = json.loads((java / "traceability.json").read_text(encoding="utf-8"))
    arts = {a["symbol"]: a for a in manifest["artifacts"]}

    assert all((java / a["file"]).is_file() for a in manifest["artifacts"])  # every cited file was generated
    endpoint = arts["MenuController#transactionMENU"]
    assert endpoint["facts"][0]["source"].startswith("csd/APP.csd:")
    assert endpoint["facts"][0]["ledger_field"] == "entry transactions"
    assert "(" in endpoint["facts"][0]["field_testing"]  # e.g. "open (4 public / 0 private estates)"
    assert any("no COMMAREA layout" in t for t in endpoint["todos"])  # MENU declares no DFHCOMMAREA
    link = arts["MenuService#linkAcctinq"]
    assert link["facts"][0]["source"] == "cbl/MENU.cbl:8" and link["facts"][0]["ledger_field"] == "call targets"
    field = arts["AcctCommarea#caAcctId"]
    assert field["facts"][0]["item"] == "CA-ACCT-ID @0+11" and field["facts"][0]["ledger_field"] == "record fields"
    assert manifest["summary"]["artifacts"] == len(manifest["artifacts"])
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert f"Traceability (#3650)    : {manifest['summary']['artifacts']} artifacts" in audit
