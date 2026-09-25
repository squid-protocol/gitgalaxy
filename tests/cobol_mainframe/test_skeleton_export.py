"""#3614: the verified skeleton hand-off (gitgalaxy/tools/cobol_to_cobol/skeleton_export.py).

The refractor, run against the engine (--galaxy-db / --scan), writes one skeleton per
program plus estate.json; each section names its ground-truth ledger field and carries
that field's field-testing record; the Java generator hands the skeleton to the agent
tickets and reports it in its audit. A real galaxyscope scan of a small CICS + batch
fixture backs the end-to-end tests.
"""

import inspect
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import EngineCall, EngineFile, GalaxyIR, scan_to_db
from gitgalaxy.tools.cobol_to_cobol.skeleton_export import (
    ESTATE_JOINS,
    FILE_CHANNELS,
    PROGRAM_JOINS,
    SkeletonExporter,
    load_confidence,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge import generate_java_agent_ticket

MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COMM.
           05 WS-ACCT-ID PIC 9(11).
       PROCEDURE DIVISION.
       000-MAIN.
           MOVE 1 TO WS-ACCT-ID.
           EXEC CICS LINK PROGRAM('ACCTINQ') COMMAREA(WS-COMM) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

ACCTINQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC PIC X(80).
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05 CA-ACCT-ID PIC 9(11).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS READ FILE('ACCTDAT') INTO(WS-REC) RIDFLD(CA-ACCT-ID) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("skeleton")
    repo = base / "estate"
    for rel, text in {"cbl/MENU.cbl": MENU, "cbl/ACCTINQ.cbl": ACCTINQ}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_every_section_maps_to_a_ledger_field_the_confidence_file_records():
    fields = set(load_confidence())
    mapped = {f for _, f in FILE_CHANNELS.values()} | {f for _, f in PROGRAM_JOINS.values()}
    assert mapped | set(ESTATE_JOINS.values()) <= fields


def test_every_join_is_an_argument_free_galaxy_ir_method():
    for method in [m for m, _ in PROGRAM_JOINS.values()] + list(ESTATE_JOINS):
        params = list(inspect.signature(getattr(GalaxyIR, method)).parameters.values())[1:]
        assert all(p.default is not inspect.Parameter.empty for p in params), method
    for attr, _ in FILE_CHANNELS.values():
        assert attr in EngineFile.__dataclass_fields__, attr


def test_a_program_gets_its_own_rows_of_each_join_with_the_fields_testing_status(tmp_path):
    call = EngineCall("LINK", "literal", "'B'", "B", "B.cbl", 9)
    files = {
        "A.cbl": EngineFile("A.cbl", "cobol", 10, program_ids=["A"], calls=[call]),
        "B.cbl": EngineFile("B.cbl", "cobol", 5, program_ids=["B"]),
    }
    confidence = {"call targets": {"status": "open", "tested_on_public": 6, "tested_on_private": 1}}
    exporter = SkeletonExporter(GalaxyIR(tmp_path / "x.db", "r", "c0ffee", files), confidence)
    a = exporter.program(files["A.cbl"])
    assert a["program"]["program_ids"] == ["A"] and a["source"]["commit"] == "c0ffee"
    calls = a["sections"]["calls"]
    assert (calls["ledger_field"], calls["field_testing"], calls["tested_on_public"], calls["tested_on_private"]) == (
        "call targets",
        "open",
        6,
        1,
    )
    assert calls["facts"][0]["target"] == "B" and calls["facts"][0]["resolves_to"] == "B.cbl"
    # a field the confidence file does not know is `untested`, never assumed good
    assert a["sections"]["records"]["field_testing"] == "untested"
    b = exporter.program(files["B.cbl"])
    assert b["sections"]["calls"]["facts"] == []


def test_the_refractor_writes_skeletons_that_carry_the_engine_facts(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    skel = clean / "06_skeleton"
    assert sorted(p.name for p in skel.iterdir()) == ["ACCTINQ_skeleton.json", "MENU_skeleton.json", "estate.json"]

    menu = json.loads((skel / "MENU_skeleton.json").read_text(encoding="utf-8"))
    assert [(c["verb"], c["target"], c["resolves_to"]) for c in menu["sections"]["calls"]["facts"]] == [
        ("LINK", "ACCTINQ", "cbl/ACCTINQ.cbl")
    ]
    (contract,) = menu["sections"]["commarea_contracts"]["facts"]
    assert (contract["caller"], contract["callee"], contract["commarea"]) == (
        "cbl/MENU.cbl",
        "cbl/ACCTINQ.cbl",
        "WS-COMM",
    )
    acct = json.loads((skel / "ACCTINQ_skeleton.json").read_text(encoding="utf-8"))
    assert [r["name"] for r in acct["sections"]["cics_resources"]["facts"]] == ["ACCTDAT"]
    # the callee sees the contract too: the join is filtered by every key naming the program
    assert [c["caller"] for c in acct["sections"]["commarea_contracts"]["facts"]] == ["cbl/MENU.cbl"]
    for section in menu["sections"].values():
        assert section["field_testing"] in ("field-tested", "open", "untested")

    estate = json.loads((skel / "estate.json").read_text(encoding="utf-8"))
    assert set(estate["sections"]) == set(ESTATE_JOINS) and "score" in estate["completeness"]
    report = (clean / "03_audit_reports" / "master_refraction_audit.txt").read_text(encoding="utf-8")
    assert "Verified skeletons (06_skeleton): 2 programs + estate.json" in report


def test_without_the_engine_no_skeleton_is_written(scanned, tmp_path):
    repo, _ = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    assert not (clean / "06_skeleton").exists()


SLICE = {"target_var": "WS-ACCT-ID", "business_rules": [{"paragraph": "000-MAIN", "statement": "MOVE 1 TO X"}]}


def test_the_agent_ticket_carries_the_skeleton_without_the_bulk_sections():
    section = {"ledger_field": "call targets", "field_testing": "open", "tested_on_public": 6, "tested_on_private": 0}
    skeleton = {
        "program": {"file": "cbl/MENU.cbl", "program_ids": ["MENU"]},
        "sections": {
            "calls": {**section, "facts": [{"verb": "LINK", "target": "ACCTINQ"}]},
            "mq_calls": {**section, "facts": []},
            "data_flows": {**section, "facts": [{"verb": "MOVE"}]},
        },
    }
    plain = generate_java_agent_ticket(SLICE, "MENU")
    ticket = generate_java_agent_ticket(
        SLICE, "MENU", skeleton=skeleton, skeleton_file="x/06_skeleton/MENU_skeleton.json"
    )
    view = ticket["context"]["verified_skeleton"]
    assert list(view["sections"]) == ["calls"]  # empty and bulk sections left out
    assert view["sections"]["calls"]["field_testing"] == "open"
    assert view["full_skeleton"] == "x/06_skeleton/MENU_skeleton.json"
    assert ticket["system_prompt"].startswith(plain["system_prompt"]) and "verified_skeleton" in ticket["system_prompt"]
    assert "verified_skeleton" not in plain["context"]  # no skeleton: the ticket is unchanged


def test_the_java_generator_uses_the_skeleton(scanned, tmp_path):
    from gitgalaxy import cobol_to_java_controller

    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db), "--var", "WS-ACCT-ID"]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    with patch("sys.argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        cobol_to_java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "[2] VERIFIED SKELETON" in audit and "Programs with a skeleton : 2" in audit
    assert "call targets" in audit
    ticket = json.loads((java / "ai_agent_jobs" / "MENU_java_service_job.json").read_text(encoding="utf-8"))
    skeleton = ticket["context"]["verified_skeleton"]
    assert skeleton["program"]["program_ids"] == ["MENU"]
    assert skeleton["full_skeleton"] == f"{clean.name}/06_skeleton/MENU_skeleton.json"
    assert Path(tmp_path, skeleton["full_skeleton"]).is_file()
