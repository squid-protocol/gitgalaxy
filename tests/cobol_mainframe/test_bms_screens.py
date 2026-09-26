"""#3619: BMS screens -> view models, service handlers and (per ui.flavour) web views.

A real scan of a small estate: one mapset with a label, an input field (IC), a numeric
input, a dark field and an OCCURS field; a program that RECEIVEs and SENDs the map, and
SENDs a map no BMS source defines. Pinned: the view model (LAYOUT, properties, the
symbolic-map citation), the render / submit handlers, the unresolved map's TODO, each
flavour's controller / template / build dependencies, the manifest and the worklist.
The generated Java is compiled by java_target_matrix (ui-thymeleaf / ui-openapi-plain).
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.java_target import ConfigError, target_from_dict

BMS = (
    "\n".join(
        [
            "SGN00    DFHMSD TYPE=&SYSPARM,LANG=COBOL,MODE=INOUT,STORAGE=AUTO",
            "SGN0A    DFHMDI SIZE=(24,80),LINE=1,COLUMN=1",
            "         DFHMDF POS=(1,1),LENGTH=6,ATTRB=(ASKIP,NORM),INITIAL='Tran :',".ljust(71) + "X",  # col 72
            "               COLOR=BLUE",
            "USERID   DFHMDF POS=(19,43),LENGTH=8,ATTRB=(FSET,IC,NORM,UNPROT)",
            "AMOUNT   DFHMDF POS=(20,43),LENGTH=5,ATTRB=(NUM,UNPROT)",
            "PASSWD   DFHMDF POS=(21,43),LENGTH=8,ATTRB=(DRK,FSET,UNPROT)",
            "ITEMS    DFHMDF POS=(22,1),LENGTH=3,OCCURS=2",
            "         DFHMSD TYPE=FINAL",
            "         END",
        ]
    )
    + "\n"
)

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SGNON.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-X               PIC X.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RECEIVE MAP('SGN0A') MAPSET('SGN00') INTO(SGN0AI)
                END-EXEC.
           EXEC CICS SEND MAP('SGN0A') MAPSET('SGN00') FROM(SGN0AO) ERASE
                END-EXEC.
           EXEC CICS SEND MAP('GHOST') MAPSET('NOSUCH') END-EXEC.
           EXEC CICS SEND MAP('SGN00') MAPONLY END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

CSD = " DEFINE TRANSACTION(SGN0) GROUP(APP)\n        PROGRAM(SGNON)\n"


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("bms_screens")
    repo = base / "estate"
    for rel, text in {"bms/SGN00.bms": BMS, "cbl/SGNON.cbl": PROGRAM, "csd/APP.csd": CSD}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def _generate(scanned, tmp_path, flavour=None):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    argv = ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]
    if flavour:
        cfg = tmp_path / "ui.json"
        cfg.write_text(json.dumps({"ui": {"flavour": flavour}}), encoding="utf-8")
        argv += ["--config", str(cfg)]
    with patch.object(sys, "argv", argv):
        java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    return java


SRC = "src/main/java/com/gitgalaxy/modernized"


def test_the_view_model_and_the_handlers(scanned, tmp_path):
    java = _generate(scanned, tmp_path)
    vm = (java / SRC / "dto/screen/Sgn0aScreen.java").read_text(encoding="utf-8")
    assert "BMS map SGN0A of mapset SGN00 (bms/SGN00.bms)" in vm
    assert 'new ScreenField(null, 1, 1, 6, false, false, false, false, false, "Tran :", "BLUE", 1)' in vm  # label
    assert 'new ScreenField("USERID", 19, 43, 8, true, false, false, false, true, null, null, 1)' in vm  # IC input
    assert 'new ScreenField("AMOUNT", 20, 43, 5, true, true, false, false, false, null, null, 1)' in vm  # NUM
    assert 'new ScreenField("PASSWD", 21, 43, 8, true, false, false, true, false, null, null, 1)' in vm  # DRK
    assert "private List<String> items;" in vm and "private String userid;" in vm  # OCCURS=2 -> a list
    assert "Symbolic map USERIDI, USERIDO." in vm
    assert "@Size" not in vm  # ui.flavour none: no validator on the classpath, no annotations
    svc = (java / SRC / "service/SgnonService.java").read_text(encoding="utf-8")
    assert "public Sgn0aScreen renderSgn0a(Sgn0aScreen screen) {" in svc
    assert "public ScreenModel submitSgn0a(Sgn0aScreen input, String aid) {" in svc
    assert "        return renderSgn0a(input);" in svc  # the program also SENDs the map it RECEIVEs
    assert "RECEIVE MAP(SGN0A) MAPSET(SGN00) INTO(SGN0AI) at cbl/SGNON.cbl:8" in svc
    assert "SEND MAP GHOST (mapset NOSUCH) at cbl/SGNON.cbl:12: no single BMS source defines it" in svc
    # the mapset's name sent as a map (CBSA BNK1CCS's CLEAR branch): the maps the mapset does define
    assert (
        "SEND MAP SGN00 (mapset SGN00) at cbl/SGNON.cbl:13: no single BMS source defines it (candidates: none "
        "in the repository); mapset SGN00 defines SGN0A" in svc
    )
    assert not (java / SRC / "controller/screen").exists() and not (java / "src/main/resources/templates").exists()
    assert "  • BMS screens (#3619)      : 1 view models (4 fields) for 1 programs" in (
        java / "java_migration_audit.txt").read_text(encoding="utf-8")  # fmt: skip

    manifest = json.loads((java / "traceability.json").read_text(encoding="utf-8"))
    kinds = {a["kind"] for a in manifest["artifacts"]}
    assert {"screen-view-model", "screen-field", "screen-send", "screen-receive"} <= kinds
    field = next(a for a in manifest["artifacts"] if a["symbol"] == "Sgn0aScreen#userid")
    assert field["facts"][0]["source"] == "bms/SGN00.bms:5" and field["facts"][0]["ledger_field"] == "BMS screen fields"
    worklist = json.loads((java / "migration_worklist.json").read_text(encoding="utf-8"))
    cats = {i["category"] for i in worklist["items"] if "Sgnon" in i["file"]}
    assert {"business-logic", "missing-layout"} <= cats  # the handlers' TODOs; the GHOST map


def test_thymeleaf_adds_pages_validation_and_its_starters(scanned, tmp_path):
    java = _generate(scanned, tmp_path, "thymeleaf")
    vm = (java / SRC / "dto/screen/Sgn0aScreen.java").read_text(encoding="utf-8")
    assert "    @Size(max = 8)\n    private String userid;" in vm
    assert '    @Size(max = 5)\n    @Pattern(regexp = "[0-9 ]*")\n    private String amount;' in vm
    ctl = (java / SRC / "controller/screen/SgnonScreenController.java").read_text(encoding="utf-8")
    assert '@RequestMapping("/screens/sgnon")' in ctl and "@Controller" in ctl
    assert "ScreenModel next = sgnonService.submitSgn0a(Sgn0aScreen.fromValues(form), aid);" in ctl
    page = (java / "src/main/resources/templates/screen.html").read_text(encoding="utf-8")
    assert 'th:each="c : ${cells}"' in page and 'value="PF3"' in page
    pom = (java / "pom.xml").read_text(encoding="utf-8")
    assert "spring-boot-starter-thymeleaf" in pom and "spring-boot-starter-validation" in pom


def test_openapi_only_adds_rest_endpoints_and_springdoc(scanned, tmp_path):
    java = _generate(scanned, tmp_path, "openapi-only")
    ctl = (java / SRC / "controller/screen/SgnonScreenController.java").read_text(encoding="utf-8")
    assert '@RequestMapping("/api/v1/sgnon/screens")' in ctl and "@RestController" in ctl
    assert "public ScreenModel submitSgn0a(@Valid @RequestBody Sgn0aScreen input," in ctl
    assert not (java / "src/main/resources/templates").exists()
    pom = (java / "pom.xml").read_text(encoding="utf-8")
    assert "springdoc-openapi-starter-webmvc-ui" in pom and "<version>2.5.0</version>" in pom


def test_a_ui_flavour_needs_the_services_and_controllers():
    with pytest.raises(ConfigError, match="ui.flavour 'thymeleaf' needs features.services"):
        target_from_dict({"ui": {"flavour": "thymeleaf"}, "features": {"rest_controllers": False}})
    with pytest.raises(ConfigError, match="choose one of none, thymeleaf, openapi-only"):
        target_from_dict({"ui": {"flavour": "react"}})
