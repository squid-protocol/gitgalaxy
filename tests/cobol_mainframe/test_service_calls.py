"""#3616: LINK / XCTL / CALL -> service-to-service calls, plus the engine fix it found.

A real galaxyscope scan of a small estate backs the tests:
- MENU LINKs to ACCTINQ (static), LINKs to AUDIT (which the CSD routes to region AOR1),
  CALLs SUBPGM USING two items, and XCTLs to a program name MOVEd from literals.
- The CSD deck also DEFINEs every program, which used to make the deck the "file" of each
  program in dynamic_call_targets.
- Two SUBPGMs in different directories exercise the nearest-declarer rule.

Compiling the generated Java is the compile matrix's job (java_target_matrix.py --scan).
"""

import json
import shutil
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.java_target import ConfigError, target_from_dict

MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COMM.
           05 WS-ACCT-ID      PIC 9(11).
       01  WS-A               PIC X(8).
       01  WS-B.
           05 WS-B1           PIC 9(4).
           05 WS-B2           PIC X(10).
       01  WS-NEXT            PIC X(8).
       01  WS-OPT             PIC 9.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS LINK PROGRAM('ACCTINQ') COMMAREA(WS-COMM) END-EXEC.
           EXEC CICS LINK PROGRAM('AUDIT') COMMAREA(WS-COMM) END-EXEC.
           CALL 'SUBPGM' USING WS-A WS-B.
           IF WS-OPT = 1
               MOVE 'ACCTINQ' TO WS-NEXT
           ELSE
               MOVE 'ACCTUPD' TO WS-NEXT
           END-IF.
           EXEC CICS XCTL PROGRAM(WS-NEXT) COMMAREA(WS-COMM) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


def _callee(name: str) -> str:
    return f"""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {name}.
       DATA DIVISION.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
           05 LK-ACCT-ID      PIC 9(11).
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""


SUBPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUBPGM.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-A               PIC X(8).
       01  LK-B.
           05 LK-B1           PIC 9(4).
           05 LK-B2           PIC X(10).
       PROCEDURE DIVISION USING LK-A LK-B.
       000-MAIN.
           GOBACK.
"""

CSD = """\
 DEFINE TRANSACTION(MENU) GROUP(APP)
        PROGRAM(MENU)
 DEFINE PROGRAM(MENU) GROUP(APP)
 DEFINE PROGRAM(ACCTINQ) GROUP(APP)
 DEFINE PROGRAM(ACCTUPD) GROUP(APP)
 DEFINE PROGRAM(AUDIT) GROUP(APP)
        REMOTESYSTEM(AOR1)
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("service_calls")
    repo = base / "estate"
    files = {
        "cbl/MENU.cbl": MENU,
        "cbl/ACCTINQ.cbl": _callee("ACCTINQ"),
        "cbl/ACCTUPD.cbl": _callee("ACCTUPD"),
        "cbl/AUDIT.cbl": _callee("AUDIT"),
        "cbl/SUBPGM.cbl": SUBPGM,
        "other/deep/SUBPGM.cbl": SUBPGM,
        "csd/APP.csd": CSD,
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


# ---- the engine fix ---------------------------------------------------------------------------
def test_a_csd_deck_is_not_the_file_of_the_programs_it_defines(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    assert set(ir.files["csd/APP.csd"].program_ids) >= {"ACCTINQ", "ACCTUPD"}  # the deck names them ...
    (site,) = [d for d in ir.dynamic_call_targets() if d["file"] == "cbl/MENU.cbl"]
    assert [(c["program"], c["resolves_to"]) for c in site["candidates"]] == [
        ("ACCTINQ", "cbl/ACCTINQ.cbl"),  # ... but the COBOL source declares them
        ("ACCTUPD", "cbl/ACCTUPD.cbl"),
    ]
    assert ir._program_file("ACCTINQ") == "cbl/ACCTINQ.cbl"  # one declarer, not two


def test_two_declarers_resolve_to_the_nearest_or_to_none(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    assert ir._nearest_program("SUBPGM", "cbl/MENU.cbl") == "cbl/SUBPGM.cbl"
    assert ir._nearest_program("SUBPGM", "other/deep/X.cbl") == "other/deep/SUBPGM.cbl"
    assert ir._nearest_program("SUBPGM", "third/X.cbl") is None  # tied: not guessed
    assert ir._nearest_program("NOSUCH", "cbl/MENU.cbl") is None


def test_program_interfaces_carry_the_using_parameters(scanned):
    _, db = scanned
    params = load_galaxy_ir(db).program_interfaces()["cbl/SUBPGM.cbl"]["parameters"]
    assert [(p["position"], p["name"], p["mode"], p["layout"]["bytes"]) for p in params] == [
        (1, "LK-A", "REFERENCE", 8),
        (2, "LK-B", "REFERENCE", 14),
    ]


# ---- the Java ---------------------------------------------------------------------------------
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
    return java, java / "src/main/java/com/gitgalaxy/modernized"


def test_calls_become_service_calls(scanned, tmp_path):
    java, src = _java(scanned, tmp_path)
    menu = (src / "service/MenuService.java").read_text(encoding="utf-8")
    # a static LINK: the target's handleLink, through a cycle-safe ObjectProvider
    assert "private final ObjectProvider<AcctinqService> acctinqService;" in menu
    # ACCTINQ receives what MENU passes (WS-COMM, named after MENU, which declares it): no mapping needed
    assert "public MenuWsComm linkAcctinq(MenuWsComm request) {" in menu
    assert "return acctinqService.getObject().handleLink(request);" in menu
    assert "/** EXEC CICS LINK PROGRAM(ACCTINQ) at cbl/MENU.cbl:" in menu
    # a CALL: typed by the callee's USING items (an elementary item maps to its Java type). Two
    # SUBPGMs exist; the engine resolved this one to cbl/SUBPGM.cbl, the clean room keys it cbl__SUBPGM
    assert "/** CALL 'SUBPGM' at cbl/MENU.cbl:" in menu
    assert "public void callCblSubpgm(String lkA, CblSubpgmLkB lkB) {" in menu
    assert "cblSubpgmService.getObject().handleCall(lkA, lkB);" in menu
    sub = (src / "service/CblSubpgmService.java").read_text(encoding="utf-8")
    assert "public void handleCall(String lkA, CblSubpgmLkB lkB) {" in sub
    # the data-driven XCTL: a switch over the candidates, anything else refused
    assert "public Object dispatchWsNextL" in menu
    assert 'case "ACCTUPD":' in menu and "acctupdService.getObject().handleLink((AcctupdDfhcommarea) request)" in menu
    # ACCTUPD is reached only through the data-driven XCTL, so it was resolved to its own DFHCOMMAREA:
    # the record this site passes differs, and the case says so rather than hiding it
    assert "TODO: this site passes WS-COMM; ACCTUPD receives DFHCOMMAREA (cbl/ACCTUPD.cbl)" in menu
    assert "no known target" in menu
    # the remote DPL LINK: a client for region AOR1
    assert "private final Aor1RemoteClient aor1RemoteClient;" in menu
    assert "return aor1RemoteClient.linkAudit(request);" in menu
    client = (src / "client/Aor1RemoteClient.java").read_text(encoding="utf-8")
    assert '@Value("${gitgalaxy.remote.aor1.url:http://localhost:8080}")' in client
    assert 'rest.postForObject(baseUrl + "/api/v1/audit/link", request, MenuWsComm.class)' in client
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "Service calls (#3616)    : 1 LINK, 0 XCTL, 1 CALL, 1 data-driven dispatch, 1 remote; 1 remote" in audit


def test_local_remote_calls_and_plain_constructors(scanned, tmp_path):
    _, src = _java(scanned, tmp_path, {"integration": {"remote_calls": "local"}, "java": {"data_classes": "plain"}})
    menu = (src / "service/MenuService.java").read_text(encoding="utf-8")
    assert not (src / "client").exists()
    assert "return auditService.getObject().handleLink(request);" in menu  # in-process
    assert "public MenuService(ObjectProvider<CblSubpgmService> cblSubpgmService, " in menu  # plain: explicit ctor
    assert "this.acctinqService = acctinqService;" in menu


def test_the_remote_calls_setting_is_validated():
    with pytest.raises(ConfigError, match="integration.remote_calls"):
        target_from_dict({"integration": {"remote_calls": "grpc"}})
