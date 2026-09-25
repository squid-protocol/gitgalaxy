"""#3615: CICS transactions + COMMAREA / channel contracts -> REST endpoints and DTOs.

A real galaxyscope scan of a small CICS estate backs the tests:
- MENU is entered by CSD transaction MENU and LINKs to ACCTINQ, passing ACCT-COMMAREA from a copybook.
- ACCTINQ receives that record as its DFHCOMMAREA.
- CHANPGM is entered by transaction CHAN and exchanges containers on a channel.
- BATCH is plain batch.

The engine side (GalaxyIR.program_interfaces) and the Java side (the transaction forge,
via the cobol-to-java controller) are each pinned. Compiling the result is the Java
compile matrix's job (tests/tools/java_target_matrix.py --scan, in CI).
"""

import json
import shutil
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CicsForge, java_type, load_skeletons
from gitgalaxy.tools.cobol_to_java.java_target import target_from_dict

ACCTCOM = """\
       01  ACCT-COMMAREA.
           05 CA-ACCT-ID      PIC 9(11).
           05 CA-BALANCE      PIC S9(9)V99 COMP-3.
           05 FILLER          PIC X(4).
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
           05 LK-BALANCE      PIC S9(9)V99 COMP-3.
           05 FILLER          PIC X(4).
           05 LK-NAME         PIC X(20).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""

CHANPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CHANPGM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REQ.
           05 REQ-ID          PIC X(8).
       01  WS-RESP.
           05 RESP-CODE       PIC 9(4) COMP.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS GET CONTAINER('REQ.DATA') CHANNEL('CHAN1') INTO(WS-REQ) END-EXEC.
           EXEC CICS PUT CONTAINER('RESP') CHANNEL('CHAN1') FROM(WS-RESP) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

BATCH = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BATCH.
       PROCEDURE DIVISION.
       000-MAIN.
           DISPLAY 'HI'.
           STOP RUN.
"""

CSD = """\
 DEFINE TRANSACTION(MENU) GROUP(APP)
        PROGRAM(MENU) PROFILE(DFHCICST)
 DEFINE TRANSACTION(CHAN) GROUP(APP)
        PROGRAM(CHANPGM)
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("cics_endpoints")
    repo = base / "estate"
    files = {
        "cbl/MENU.cbl": MENU,
        "cbl/ACCTINQ.cbl": ACCTINQ,
        "cbl/CHANPGM.cbl": CHANPGM,
        "cbl/BATCH.cbl": BATCH,
        "cpy/ACCTCOM.cpy": ACCTCOM,
        "csd/APP.csd": CSD,
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_program_interfaces_name_what_each_program_receives(scanned):
    _, db = scanned
    interfaces = load_galaxy_ir(db).program_interfaces()
    acct = interfaces["cbl/ACCTINQ.cbl"]["commarea"]
    # what the resolved caller passes wins over the callee's own declaration
    assert (acct["record"], acct["file"], acct["basis"], acct["bytes"]) == (
        "ACCT-COMMAREA",
        "cpy/ACCTCOM.cpy",
        "caller_record",
        41,
    )
    assert acct["sources"] == [{"caller": "cbl/MENU.cbl", "line": 8, "verb": "LINK"}]
    assert [f["name"] for f in acct["fields"]] == ["CA-ACCT-ID", "CA-BALANCE", "FILLER", "CA-NAME"]
    assert [f["offset"] for f in acct["fields"]] == [0, 11, 17, 21]
    menu = interfaces["cbl/MENU.cbl"]
    assert menu["commarea"] is None and "no LINKAGE DFHCOMMAREA" in menu["commarea_gap"]
    chan = interfaces["cbl/CHANPGM.cbl"]["containers"]
    assert [(c["container"], c["channel"], c["direction"], c["record"]) for c in chan] == [
        ("REQ.DATA", "CHAN1", "in", "WS-REQ"),
        ("RESP", "CHAN1", "out", "WS-RESP"),
    ]
    assert chan[1]["layout"]["fields"][0]["class"] == "B"


@pytest.mark.parametrize(
    "fld, expected",
    [
        ({"class": "X", "pic": "X(20)"}, "String"),
        ({"class": "9", "pic": "9(11)"}, "Long"),
        ({"class": "9", "pic": "9(4)"}, "Integer"),
        ({"class": "P", "pic": "S9(9)V99"}, "BigDecimal"),
        ({"class": "9", "pic": "9(19)"}, "BigDecimal"),
        ({"class": "9", "pic": "ZZ,ZZ9.99"}, "String"),
        ({"class": "9", "pic": "9990"}, "String"),  # the insertion 0 is an editing symbol
        ({"class": "9", "pic": "9(3)0"}, "String"),
        ({"class": "9", "pic": "S9(10)"}, "Long"),
        ({"class": "B", "pic": "S9(4)"}, "Integer"),
        ({"class": "F", "pic": None}, "Double"),
    ],
)
def test_java_types_follow_the_picture(fld, expected):
    assert java_type(fld) == expected


def _java(scanned, tmp_path, config=None):
    from gitgalaxy import cobol_to_java_controller

    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    argv = ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]
    if config:
        cfg = tmp_path / "t.json"
        cfg.write_text(json.dumps(config), encoding="utf-8")
        argv += ["--config", str(cfg)]
    with patch("sys.argv", argv):
        cobol_to_java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    return clean, java / "src/main/java/com/gitgalaxy/modernized"


def test_a_transaction_becomes_an_endpoint_and_a_link_target_takes_the_commarea(scanned, tmp_path):
    clean, src = _java(scanned, tmp_path)
    menu = (src / "controller/MenuController.java").read_text(encoding="utf-8")
    assert '@PostMapping("/transactions/MENU")' in menu
    assert 'menuService.handleTransaction("MENU")' in menu and "ResponseEntity<Void>" in menu
    assert "TODO: no COMMAREA layout: no LINKAGE DFHCOMMAREA" in menu
    assert "(CSD csd/APP.csd:" in menu

    acct = (src / "controller/AcctinqController.java").read_text(encoding="utf-8")
    assert '@PostMapping("/link")' in acct and "LINK at cbl/MENU.cbl:8" in acct
    assert "public ResponseEntity<AcctCommarea> link(@RequestBody AcctCommarea request)" in acct
    dto = (src / "dto/cics/AcctCommarea.java").read_text(encoding="utf-8")
    assert "// CA-ACCT-ID: PIC 9(11), offset 0, 11 bytes (cpy/ACCTCOM.cpy)" in dto
    assert "private Long caAcctId;" in dto and "private BigDecimal caBalance;" in dto
    assert "private String caName;" in dto and "filler" not in dto.lower().split("*/")[1]
    assert "as passed by LINK at cbl/MENU.cbl:8" in dto
    service = (src / "service/AcctinqService.java").read_text(encoding="utf-8")
    assert "public AcctCommarea handleLink(AcctCommarea request) {" in service

    chan = (src / "controller/ChanpgmController.java").read_text(encoding="utf-8")
    assert "ResponseEntity<ChanpgmChannelOut> transactionCHAN(@RequestBody ChanpgmChannelIn request)" in chan
    chan_in = (src / "dto/cics/ChanpgmChannelIn.java").read_text(encoding="utf-8")
    assert "private ChanpgmWsReq reqData;" in chan_in and "CONTAINER(REQ.DATA)" in chan_in

    assert not (src / "controller/BatchController.java").exists()  # batch: the generic path, unchanged
    audit = (src.parents[5] / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "CICS programs (#3615)    : 3 -- 1 with a COMMAREA DTO, 2 transaction endpoints" in audit
    assert set(load_skeletons(clean / "06_skeleton")) == {"MENU", "ACCTINQ", "CHANPGM", "BATCH"}


def test_the_target_style_reaches_the_cics_dtos(scanned, tmp_path):
    _, src = _java(scanned, tmp_path, {"java": {"data_classes": "plain", "dto_style": "record"}})
    dto = (src / "dto/cics/AcctCommarea.java").read_text(encoding="utf-8")
    assert "public record AcctCommarea(" in dto and "lombok" not in dto
    acct = (src / "controller/AcctinqController.java").read_text(encoding="utf-8")
    assert "public AcctinqController(AcctinqService acctinqService)" in acct


def _skeleton(file, record_file, fields, **sections):
    layout = {"bytes": 4, "variable": False, "extended": False, "unexpanded": [], "copybooks": [], "fields": fields}
    commarea = {"record": "SHARED-AREA", "file": record_file, "basis": "caller_record", "alternatives": [],
                "sources": [{"caller": "X.cbl", "line": 1, "verb": "LINK"}], **layout}  # fmt: skip
    sec = {"field_testing": "open", "tested_on_public": 1, "tested_on_private": 0}
    return {
        "program": {"file": file, "program_ids": [file[:-4]]},
        "sections": {
            "interface": {**sec, "facts": {"commarea": commarea, "commarea_gap": None, "containers": []}},
            "commarea_contracts": {**sec, "facts": [{"callee": file, "verb": "LINK", "caller": "X.cbl", "line": 1}]},
            **sections,
        },
    }


def test_one_dto_serves_every_program_passed_the_same_copybook_record():
    fld = [{"name": "A-B", "pic": "X(4)", "class": "X", "offset": 0, "bytes": 4, "file": "c.cpy"}]
    other = [{"name": "A-C", "pic": "X(4)", "class": "X", "offset": 0, "bytes": 4, "file": "c.cpy"}]
    forge = CicsForge(
        {
            "P1": _skeleton("P1.cbl", "c.cpy", fld),
            "P2": _skeleton("P2.cbl", "c.cpy", fld),
            "P3": _skeleton("P3.cbl", "c.cpy", other),  # same record name, another layout
        },
        "com.acme",
        target_from_dict({}),
    )
    assert [forge.programs[k].commarea_dto for k in ("P1", "P2", "P3")] == ["SharedArea", "SharedArea", "SharedArea2"]
    shared = forge.dto_sources()["SharedArea"]
    assert "The COMMAREA P1 receives" in shared and "The COMMAREA P2 receives" in shared
